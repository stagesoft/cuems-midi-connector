# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""Plain-text config for cuems-midi-connector wiring rules."""

import os
from importlib.resources import files as _resource_files

from cuemsutils.log import Logger


class MidiConnectorConfig:
    SYSTEM_PATH = "/etc/cuems/midiconnector.conf"
    VALID_DIRECTIONS = {"from_through", "to_through", "network"}

    def __init__(self, path: str | None = None):
        self.patterns: list[tuple[str, str]] = []
        self.source_path: str = path or self._pick_path()
        Logger.info(f"loading wiring rules from {self.source_path}")
        self._load(self.source_path)

    def _pick_path(self) -> str:
        if os.path.exists(self.SYSTEM_PATH):
            return self.SYSTEM_PATH
        return str(
            _resource_files("cuemsmidiconnector.data") / "midiconnector.conf.default"
        )

    def _load(self, path: str) -> None:
        with open(path, encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    Logger.warning(f"{path}:{lineno}: malformed line, skipping")
                    continue
                direction, pattern = parts[0], parts[1].strip()
                if direction not in self.VALID_DIRECTIONS:
                    Logger.warning(
                        f"{path}:{lineno}: unknown direction {direction!r}, skipping"
                    )
                    continue
                self.patterns.append((direction, pattern))

    def match(self, client_name: str) -> tuple[str, str] | None:
        """Return the first (direction, pattern) matching client_name, or None."""
        for direction, pat in self.patterns:
            if pat in client_name:
                return (direction, pat)
        return None
