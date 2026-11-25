# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

from cuemsmidiconnector.connector import CuemsMidiConnector, MASTER_IP_FILE


def test_detects_controller_when_master_ip_present(monkeypatch):
    monkeypatch.setattr(
        "cuemsmidiconnector.connector.os.path.exists",
        lambda p: p == MASTER_IP_FILE,
    )
    assert CuemsMidiConnector._detect_controller_role() is True


def test_detects_node_when_master_ip_absent(monkeypatch):
    monkeypatch.setattr(
        "cuemsmidiconnector.connector.os.path.exists", lambda p: False
    )
    assert CuemsMidiConnector._detect_controller_role() is False


def test_role_reevaluated_each_call(monkeypatch):
    """Role must be re-detected at runtime, not cached."""
    state = {"present": False}

    def fake_exists(p):
        return p == MASTER_IP_FILE and state["present"]

    monkeypatch.setattr(
        "cuemsmidiconnector.connector.os.path.exists", fake_exists
    )
    assert CuemsMidiConnector._detect_controller_role() is False
    state["present"] = True
    assert CuemsMidiConnector._detect_controller_role() is True
    state["present"] = False
    assert CuemsMidiConnector._detect_controller_role() is False
