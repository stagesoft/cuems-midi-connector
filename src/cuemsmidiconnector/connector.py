# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""ALSA seq auto-wiring daemon for CUEMS MTC distribution."""

import os

from pyalsa import alsaseq
from pyalsa.alsaseq import SequencerError

from cuemsutils.log import Logger
from cuemsutils.tools.SignalEngine import SignalEngine

from .config import MidiConnectorConfig


MASTER_IP_FILE = "/etc/cuems/master.ip"
THROUGH_PORT_NAME = "Midi Through Port-0"

# rtpmidid exposes infrastructure ports alongside per-peer relay ports.
# Names are matched after .strip() — pyalsa returns trailing-padded labels.
RTPMIDID_INFRA_PORT_NAMES = frozenset({"Network Export", "Announcements"})


def _is_busy_error(err: SequencerError) -> bool:
    """pyalsa doesn't expose errno; sniff the EBUSY message instead."""
    msg = str(err).lower()
    return "busy" in msg or "already" in msg


class GenericConnection:
    """Wires connections to/from the kernel Midi Through Port-0 client."""

    def __init__(self, seq: alsaseq.Sequencer):
        self.seq = seq
        self.through_port = self._resolve_through_port()

    def _resolve_through_port(self) -> tuple[int, int]:
        # `Midi Through Port-0` is the port name on the kernel `Midi Through`
        # client. Iterate every client's ports and match on the port name.
        # pyalsa pads names with trailing whitespace — strip before compare.
        for _client_name, client_id, ports in self.seq.connection_list():
            for port_name, port_id, _ in ports:
                if port_name.strip() == THROUGH_PORT_NAME:
                    Logger.info(
                        f"resolved {THROUGH_PORT_NAME!r} at {client_id}:{port_id}"
                    )
                    return (client_id, port_id)
        Logger.warning(
            f"{THROUGH_PORT_NAME!r} not found via name lookup; "
            "falling back to kernel default (14, 0)"
        )
        return (14, 0)

    def _connect(self, src: tuple[int, int], dst: tuple[int, int]) -> None:
        try:
            self.seq.connect_ports(src, dst)
            Logger.info(f"wired {src[0]}:{src[1]} -> {dst[0]}:{dst[1]}")
        except SequencerError as e:
            if _is_busy_error(e):
                Logger.debug(f"already connected {src} -> {dst}")
            else:
                Logger.warning(f"connect_ports({src}, {dst}) failed: {e}")

    def connect_from_through_port(self, client_id: int) -> None:
        self._connect(self.through_port, (client_id, 0))

    def connect_to_through_port(self, client_id: int) -> None:
        self._connect((client_id, 0), self.through_port)

    def connect_network_to_through_port(self, client_id: int) -> None:
        """For node hosts: wire every per-peer rtpmidid port into the local
        Midi Through hub. Peer ports are everything on the rtpmidid client
        except the well-known infrastructure ports (Network Export, used to
        export the local Midi Through outwards; Announcements, used for
        rtpmidid internal status).

        Port names returned by pyalsa carry trailing whitespace padding —
        always compare stripped."""
        match = next(
            (c for c in self.seq.connection_list() if c[1] == client_id), None
        )
        if match is None:
            Logger.warning(f"client {client_id} disappeared before network wiring")
            return
        _, _, ports = match
        wired_any = False
        for port_name, port_id, _ in ports:
            if port_name.strip() in RTPMIDID_INFRA_PORT_NAMES:
                continue
            self._connect((client_id, port_id), self.through_port)
            wired_any = True
        if not wired_any:
            Logger.warning(
                f"no peer ports found on rtpmidid client {client_id}; "
                "wiring stays dormant until a peer announces"
            )


class CuemsMidiConnector(SignalEngine):
    """Listens to ALSA seq topology events and auto-wires MTC paths."""

    def __init__(self):
        super().__init__(with_signals=True)
        # SignalEngine.stop() writes self.stop_requested but never
        # pre-initialises it. Set both flags explicitly.
        self.running = False
        self.stop_requested = False

        self.controller = self._detect_controller_role()
        Logger.info(
            f"controller={self.controller} "
            f"(via {'presence' if self.controller else 'absence'} of {MASTER_IP_FILE})"
        )

        self.config = MidiConnectorConfig()

        self.seq = alsaseq.Sequencer(clientname="CuemsMidiConnector")
        input_id = self.seq.create_simple_port(
            name="input",
            type=alsaseq.SEQ_PORT_TYPE_MIDI_GENERIC | alsaseq.SEQ_PORT_TYPE_APPLICATION,
            caps=alsaseq.SEQ_PORT_CAP_WRITE | alsaseq.SEQ_PORT_CAP_SUBS_WRITE,
        )
        self.seq.connect_ports(
            (alsaseq.SEQ_CLIENT_SYSTEM, alsaseq.SEQ_PORT_SYSTEM_ANNOUNCE),
            (self.seq.client_id, input_id),
        )
        self.client_id = self.seq.client_id

        self.connector = GenericConnection(self.seq)

    @staticmethod
    def _detect_controller_role() -> bool:
        return os.path.exists(MASTER_IP_FILE)

    def list_clients(self) -> None:
        Logger.info("scanning current ALSA seq clients for wiring")
        for client_name, client_id, _ports in self.seq.connection_list():
            Logger.debug(f"startup client: {client_name} (id={client_id})")
            self.process_connections(client_id)
        Logger.info("startup scan complete")

    def new_client(self, data: dict) -> None:
        Logger.debug(f"new client/port event: {data}")
        client_id = data.get("addr.client")
        if client_id is not None:
            self.process_connections(client_id)

    def port_unsubscribed(self, data: dict) -> None:
        for key in ("connect.sender.client", "connect.dest.client"):
            client_id = data.get(key)
            if client_id is not None:
                self.process_connections(client_id)

    def process_connections(self, client_id: int) -> None:
        try:
            client_info = self.seq.get_client_info(client_id)
        except SequencerError as e:
            Logger.debug(f"client {client_id} vanished before lookup: {e}")
            return
        client_name = client_info.get("name", "")
        match = self.config.match(client_name)
        if match is None:
            Logger.debug(f"no pattern match for client {client_name!r}")
            return
        direction, pattern = match
        # Re-evaluate role each event so role-flips at runtime take effect.
        self.controller = self._detect_controller_role()
        Logger.debug(
            f"matched {client_name!r} -> direction={direction} "
            f"pattern={pattern!r} controller={self.controller}"
        )

        if direction == "from_through":
            self.connector.connect_from_through_port(client_id)
        elif direction == "to_through":
            self.connector.connect_to_through_port(client_id)
        elif direction == "network":
            if self.controller:
                self.connector.connect_from_through_port(client_id)
            else:
                self.connector.connect_network_to_through_port(client_id)

    def run(self) -> None:
        self.running = True
        self.notify_systemd("READY")
        self.list_clients()
        while self.running:
            try:
                event_list = self.seq.receive_events(timeout=1024, maxevents=1)
                for event in event_list:
                    self._dispatch(event)
            except SequencerError as e:
                Logger.warning(f"ALSA seq receive_events error: {e}")
            except Exception as e:
                Logger.error(f"unexpected error in event loop: {e}")
        Logger.info("event loop exited cleanly")

    def _dispatch(self, event) -> None:
        data = event.get_data()
        if event.type == alsaseq.SEQ_EVENT_CLIENT_START:
            Logger.debug(f"client started: {data}")
            self.new_client(data)
        elif event.type == alsaseq.SEQ_EVENT_PORT_START:
            Logger.debug(f"port started: {data}")
            self.new_client(data)
        elif event.type == alsaseq.SEQ_EVENT_CLIENT_EXIT:
            Logger.debug(f"client exited: {data}")
        elif event.type == alsaseq.SEQ_EVENT_PORT_EXIT:
            Logger.debug(f"port exited: {data}")
        elif event.type == alsaseq.SEQ_EVENT_PORT_SUBSCRIBED:
            Logger.debug(f"port subscribed: {data}")
        elif event.type == alsaseq.SEQ_EVENT_PORT_UNSUBSCRIBED:
            Logger.debug(f"port unsubscribed: {data}")
            self.port_unsubscribed(data)
        else:
            Logger.debug(f"unhandled event type {event.type}: {data}")
