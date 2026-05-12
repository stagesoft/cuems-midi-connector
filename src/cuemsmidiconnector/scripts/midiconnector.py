# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>

"""Entry point invoked by the cuems-midiconnector console script."""

from cuemsmidiconnector.connector import CuemsMidiConnector


def main() -> int:
    CuemsMidiConnector().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
