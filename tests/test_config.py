# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

import pytest

from cuemsmidiconnector.config import MidiConnectorConfig


def test_parses_three_directions(tmp_conf):
    path = tmp_conf(
        """
# wiring rules
from_through  Cuems Mtc Receiver
from_through  DMX_Player
to_through    MtcMaster
network       rtpmidid
"""
    )
    cfg = MidiConnectorConfig(path)
    assert ("from_through", "Cuems Mtc Receiver") in cfg.patterns
    assert ("from_through", "DMX_Player") in cfg.patterns
    assert ("to_through", "MtcMaster") in cfg.patterns
    assert ("network", "rtpmidid") in cfg.patterns
    assert len(cfg.patterns) == 4


def test_ignores_comments_and_blanks(tmp_conf):
    path = tmp_conf(
        """
# leading comment
   # indented comment
from_through  X   # trailing comment

# another
to_through    Y
"""
    )
    cfg = MidiConnectorConfig(path)
    assert cfg.patterns == [("from_through", "X"), ("to_through", "Y")]


def test_unknown_direction_skipped(tmp_conf, caplog):
    path = tmp_conf(
        """
from_through  Good
bogus_dir     Bad
to_through    AlsoGood
"""
    )
    cfg = MidiConnectorConfig(path)
    assert cfg.patterns == [("from_through", "Good"), ("to_through", "AlsoGood")]


def test_malformed_line_skipped(tmp_conf):
    path = tmp_conf(
        """
from_through  Good
lonely_token
to_through    AlsoGood
"""
    )
    cfg = MidiConnectorConfig(path)
    assert cfg.patterns == [("from_through", "Good"), ("to_through", "AlsoGood")]


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MidiConnectorConfig(str(tmp_path / "nonexistent.conf"))


def test_match_exact(tmp_conf):
    path = tmp_conf("from_through  Cuems Mtc Receiver\n")
    cfg = MidiConnectorConfig(path)
    assert cfg.match("Cuems Mtc Receiver") == (
        "from_through",
        "Cuems Mtc Receiver",
    )


def test_match_substring(tmp_conf):
    path = tmp_conf("from_through  videocomposer\n")
    cfg = MidiConnectorConfig(path)
    assert cfg.match("cuems-videocomposer:layer0") == (
        "from_through",
        "videocomposer",
    )


def test_match_none(tmp_conf):
    path = tmp_conf("from_through  Foo\nto_through    Bar\n")
    cfg = MidiConnectorConfig(path)
    assert cfg.match("nothing here") is None


def test_match_returns_first_only(tmp_conf):
    """A name that matches multiple patterns must yield only the first."""
    path = tmp_conf(
        """
from_through  Cuems
to_through    Mtc
"""
    )
    cfg = MidiConnectorConfig(path)
    # "Cuems Mtc Receiver" matches both — first wins.
    assert cfg.match("Cuems Mtc Receiver") == ("from_through", "Cuems")


def test_default_resource_used_when_system_missing(monkeypatch):
    """If /etc/cuems/midiconnector.conf is absent, package-data default is used."""
    monkeypatch.setattr(
        "cuemsmidiconnector.config.os.path.exists", lambda p: False
    )
    cfg = MidiConnectorConfig()
    # Default file ships these three direction labels at minimum.
    directions = {d for d, _ in cfg.patterns}
    assert directions == {"from_through", "to_through", "network"}
