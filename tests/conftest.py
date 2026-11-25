# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""Shared pytest fixtures for cuems-midi-connector tests."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_conf(tmp_path: Path):
    """Factory: write a wiring-rules config to a tempfile, return its path."""

    def _make(body: str) -> str:
        conf = tmp_path / "midiconnector.conf"
        conf.write_text(body, encoding="utf-8")
        return str(conf)

    return _make


class FakeSequencer:
    """Minimal stand-in for pyalsa.alsaseq.Sequencer used in routing tests."""

    def __init__(self, clients: dict[int, str] | None = None):
        self.clients = clients or {}
        self.calls: list[tuple[str, tuple, tuple]] = []

    def get_client_info(self, client_id: int) -> dict:
        if client_id not in self.clients:
            from pyalsa.alsaseq import SequencerError

            raise SequencerError(
                f"Failed to retrieve client info for '{client_id}': No such file or directory"
            )
        return {"name": self.clients[client_id]}

    def connect_ports(self, src, dst, queue=0, exclusive=0,
                      time_update=0, time_real=0) -> None:
        self.calls.append(("connect_ports", tuple(src), tuple(dst)))

    def connection_list(self) -> list[tuple[str, int, list]]:
        return [(name, cid, []) for cid, name in self.clients.items()]


@pytest.fixture
def fake_seq():
    return FakeSequencer
