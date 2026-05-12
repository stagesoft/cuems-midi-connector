# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""GenericConnection wiring decisions — especially the rtpmidid peer
discrimination logic that must handle trailing-padded port names."""

import pytest

from cuemsmidiconnector.connector import (
    GenericConnection,
    RTPMIDID_INFRA_PORT_NAMES,
    THROUGH_PORT_NAME,
)


class _RecordingSeq:
    """ALSA seq stub that records connect_ports() calls and returns a
    canned connection_list().

    `port_list` is a list of (port_name, port_id) tuples. We materialise the
    full pyalsa shape: (client_name, client_id, [(port_name, port_id, []), ...])
    """

    def __init__(self, rtpmidid_ports, through_at=(14, 0)):
        self.rtpmidid_id = 128
        self.through_at = through_at
        self.rtpmidid_ports = rtpmidid_ports
        self.calls: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def connection_list(self):
        return [
            ("Midi Through", self.through_at[0],
                [(THROUGH_PORT_NAME, self.through_at[1], [])]),
            ("rtpmidid", self.rtpmidid_id,
                [(name, pid, []) for name, pid in self.rtpmidid_ports]),
        ]

    def connect_ports(self, src, dst):
        self.calls.append((tuple(src), tuple(dst)))


@pytest.fixture
def seq_with_peers():
    """rtpmidid with a typical port mix — infra ports padded with trailing
    whitespace (as pyalsa actually returns them) plus two real peers."""
    return _RecordingSeq(rtpmidid_ports=[
        ("Network Export  ", 0),     # infra, padded
        ("Announcements", 1),         # infra
        ("controller", 2),            # peer
        ("aeon-node     ", 3),        # peer, padded
    ])


def test_resolves_through_port_with_padded_name():
    seq = _RecordingSeq(rtpmidid_ports=[("Network Export", 0)])
    # Override through_port to come back from connection_list with padding
    seq.through_at = (14, 0)

    class _PaddedSeq(_RecordingSeq):
        def connection_list(self):
            return [
                ("Midi Through", 14,
                    [("Midi Through Port-0   ", 0, [])]),  # padded
                ("rtpmidid", 128, []),
            ]

    s = _PaddedSeq(rtpmidid_ports=[])
    gc = GenericConnection(s)
    assert gc.through_port == (14, 0)


def test_network_wiring_excludes_infra_ports(seq_with_peers):
    """connect_network_to_through_port must wire `controller` and `aeon-node`
    into Midi Through, and MUST NOT wire `Network Export` or `Announcements`
    (the latter would loop, the former is rtpmidid metadata)."""
    gc = GenericConnection(seq_with_peers)
    gc.connect_network_to_through_port(seq_with_peers.rtpmidid_id)

    wired_sources = {src for src, _dst in seq_with_peers.calls}
    assert (128, 2) in wired_sources, "expected controller (port 2) to be wired"
    assert (128, 3) in wired_sources, "expected aeon-node (port 3) to be wired"
    assert (128, 0) not in wired_sources, "Network Export must NOT be wired"
    assert (128, 1) not in wired_sources, "Announcements must NOT be wired"
    # All wires must land on Midi Through Port-0
    for _src, dst in seq_with_peers.calls:
        assert dst == (14, 0)


def test_network_wiring_warns_when_no_peers(caplog):
    """If only infra ports exist (no peer yet announced), the daemon logs
    a warning and stays dormant — no wires created."""
    seq = _RecordingSeq(rtpmidid_ports=[
        ("Network Export", 0),
        ("Announcements", 1),
    ])
    gc = GenericConnection(seq)
    gc.connect_network_to_through_port(seq.rtpmidid_id)
    assert seq.calls == []


def test_network_wiring_handles_missing_client(caplog):
    """If the rtpmidid client vanishes between the event and our lookup,
    we log and return — no exception."""
    seq = _RecordingSeq(rtpmidid_ports=[("controller", 2)])
    gc = GenericConnection(seq)
    gc.connect_network_to_through_port(client_id=9999)  # not in connection_list
    assert seq.calls == []


def test_infra_port_set_does_not_include_peer_names():
    """Guard against accidentally adding a real peer name (like the
    convention 'controller') to the infra exclusion set."""
    assert "controller" not in RTPMIDID_INFRA_PORT_NAMES
    assert "master" not in RTPMIDID_INFRA_PORT_NAMES
    assert "Network Export" in RTPMIDID_INFRA_PORT_NAMES
    assert "Announcements" in RTPMIDID_INFRA_PORT_NAMES
