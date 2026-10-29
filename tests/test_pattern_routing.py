# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""Routing decisions in `process_connections` per direction."""

import pytest

from cuemsmidiconnector.config import MidiConnectorConfig
from cuemsmidiconnector.connector import CuemsMidiConnector


class _StubConnector:
    """Captures which wiring method was invoked, with the client_id."""

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def connect_from_through_port(self, client_id):
        self.calls.append(("from_through", client_id))

    def connect_to_through_port(self, client_id):
        self.calls.append(("to_through", client_id))

    def connect_network_to_through_port(self, client_id):
        self.calls.append(("network_to_through", client_id))


def _make_connector(monkeypatch, conf_body: str, *, controller: bool, clients: dict):
    """Build a CuemsMidiConnector without touching real ALSA seq."""
    monkeypatch.setattr(
        "cuemsmidiconnector.connector.os.path.exists",
        lambda p: controller and p.endswith("master.ip"),
    )
    # Bypass __init__ — we'll set the bare minimum attributes by hand.
    inst = CuemsMidiConnector.__new__(CuemsMidiConnector)
    inst.running = False
    inst.stop_requested = False
    inst.controller = controller
    # Build config from inline body.
    from tests.conftest import FakeSequencer  # noqa: F401  (just to share style)
    import tempfile, os

    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fh:
        fh.write(conf_body)
        conf_path = fh.name
    try:
        inst.config = MidiConnectorConfig(conf_path)
    finally:
        os.unlink(conf_path)
    # Inject our fake seq + stub connector.
    inst.seq = _MiniSeq(clients)
    inst.connector = _StubConnector()
    inst.pending_from_through = {}
    return inst


class _MiniSeq:
    def __init__(self, clients: dict):
        self._clients = clients

    def get_client_info(self, cid: int):
        if cid not in self._clients:
            from pyalsa.alsaseq import SequencerError

            raise SequencerError(f"missing client {cid}")
        return {"name": self._clients[cid]}


@pytest.fixture
def base_conf():
    return """
from_through  Cuems Mtc Receiver
from_through  DMX_Player
from_through  cuems-videocomposer
to_through    MtcMaster
network       rtpmidid
"""


def test_player_routes_from_through(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={132: "DMX_Player"},
    )
    inst.process_connections(132)
    assert inst.connector.calls == [("from_through", 132)]


def test_mtcmaster_routes_to_through(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={129: "MtcMaster"},
    )
    inst.process_connections(129)
    assert inst.connector.calls == [("to_through", 129)]


def test_rtpmidid_on_node_uses_network_path(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={128: "rtpmidid"},
    )
    inst.process_connections(128)
    assert inst.connector.calls == [("network_to_through", 128)]


def test_rtpmidid_on_controller_uses_from_through(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=True,
        clients={128: "rtpmidid"},
    )
    inst.process_connections(128)
    assert inst.connector.calls == [("from_through", 128)]


def test_unknown_client_not_wired(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={200: "RandomThing"},
    )
    inst.process_connections(200)
    assert inst.connector.calls == []


def test_vanished_client_silently_skipped(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={},  # nothing — get_client_info raises
    )
    inst.process_connections(999)
    assert inst.connector.calls == []


def test_role_flip_takes_effect_mid_run(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={128: "rtpmidid"},
    )
    inst.process_connections(128)
    assert inst.connector.calls == [("network_to_through", 128)]
    # Flip master.ip presence; next event must reroute.
    monkeypatch.setattr(
        "cuemsmidiconnector.connector.os.path.exists",
        lambda p: p.endswith("master.ip"),
    )
    inst.process_connections(128)
    assert inst.connector.calls[-1] == ("from_through", 128)


def test_new_client_defers_from_through(monkeypatch, base_conf):
    inst = _make_connector(
        monkeypatch,
        base_conf,
        controller=False,
        clients={132: "DMX_Player"},
    )
    inst.new_client({"addr.client": 132})
    # Deferred: NOT wired inline -- scheduled for the grace-period fallback so the
    # player's own openPort self-wires first (avoids the cold-boot EBUSY race).
    assert inst.connector.calls == []
    assert 132 in inst.pending_from_through
