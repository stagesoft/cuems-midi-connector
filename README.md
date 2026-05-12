# cuems-midi-connector

ALSA seq auto-wiring daemon for the [CUEMS](https://github.com/stagesoft/cuems-engine)
cue-management system. Listens to sequencer announce events and wires MTC
timecode connections between `Midi Through Port-0`, `rtpmidid`, `MtcMaster`,
and the per-player MTC receivers (engine, videocomposer, dmxplayer, etc.).

Runs on every CUEMS host — both controllers and nodes — bound to
`cuems-node.target` (the controller pulls the node target transitively, so a
single binding covers both roles).

## How it works

1. On startup the daemon scans the current ALSA seq client list and applies
   wiring rules from `/etc/cuems/midiconnector.conf` (or, if that file is
   absent, the bundled package-data default).
2. It subscribes to `SYSTEM:ANNOUNCE` and reacts to `CLIENT_START` /
   `PORT_START` / `PORT_UNSUBSCRIBED` events, re-evaluating wiring whenever
   the topology changes.
3. Per direction:
   - `from_through`: client receives MTC from Midi Through Port-0.
   - `to_through`: client feeds MTC into Midi Through Port-0.
   - `network`: rtpmidid bridging — direction flips by role (on a controller
     the local Midi Through feeds rtpmidid; on a node rtpmidid's relay port
     feeds the local Midi Through).

## Role detection

Controller vs node is decided at runtime by the presence of
`/etc/cuems/master.ip`. The role is re-checked on every event, so a
role-flip (operator touches/removes `master.ip`) takes effect without
restarting the daemon.

## Config file format

`/etc/cuems/midiconnector.conf` is plain text. Format:

```
# direction is one of: from_through, to_through, network
# everything after the first column is the pattern (substring match)
from_through  Cuems Mtc Receiver
from_through  DMX_Player
from_through  cuems-videocomposer
to_through    MtcMaster
network       rtpmidid
```

Lines starting with `#` are ignored. The pattern matches via substring
(`pattern in client_name`). The first matching rule wins — a client name is
wired exactly once per event.

## Build & install

This repo ships a Debian package built with `dh-virtualenv` that installs
into the shared `/usr/lib/cuems/` venv (provided by `cuems-utils`).

```bash
# Build the .deb (produces ../cuems-midi-connector_<ver>_all.deb)
debuild -b -uc -us

# Install
sudo dpkg -i ../cuems-midi-connector_*.deb
sudo systemctl daemon-reload
sudo systemctl restart cuems-midiconnector.service
```

The systemd unit `cuems-midiconnector.service` is shipped by `cuems-common`,
not by this package.

## Tests

```bash
poetry install --with dev
poetry run pytest -v
```

Tests are pure unit tests — no ALSA hardware required (the sequencer is
mocked). They cover the config parser, role detection, and routing
decisions.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
