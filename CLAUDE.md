# cuems-midi-connector

Part of the **CUEMS** ecosystem — see the [`cuems-RELATIONS`](https://github.com/stagesoft/cuems-RELATIONS) repo for the system index, architecture diagram, and protocol/port map.

## Role

ALSA seq auto-wiring daemon. Listens to sequencer announce events and wires MTC connections between `Midi Through Port-0`, `rtpmidid`, `MtcMaster`, and each player's MTC receiver (engine, videocomposer, dmxplayer, audioplayer). Python 3.11+, Poetry packaging (`src/cuemsmidiconnector/`), debian/ with dh-virtualenv, console entry `cuems-midiconnector` in the shared venv `/usr/lib/cuems/bin/`. Needs `python3-pyalsa` + `python3-systemd`.

Runs on **both controller AND nodes** via `PartOf=cuems-node.target` (the controller pulls node.target transitively). Service `cuems-midiconnector.service`.

## How it works

1. On startup, scan the current ALSA seq client list and apply wiring rules from `/etc/cuems/midiconnector.conf` (plain text; package-data fallback `data/midiconnector.conf.default`).
2. Subscribe to `SYSTEM:ANNOUNCE`; react to `CLIENT_START` / `PORT_START` / `PORT_UNSUBSCRIBED`, re-evaluating on any topology change.
3. Directions: `from_through` (client receives MTC from Midi Through Port-0), `to_through` (client feeds MTC into it), `network` (rtpmidid bridging — direction flips by role: on a controller the local Midi Through feeds rtpmidid; on a node rtpmidid's relay port feeds the local Midi Through — canonical peer port `controller`).

**Role detection** via `/etc/cuems/master.ip` presence, re-checked on every event → role flips take effect without a daemon restart. On nodes, every non-infra port of the rtpmidid client (everything except `Network Export` and `Announcements`) is wired into `Midi Through Port-0`.

## Field notes / gotchas

- **The `to_through` subscribe must use real-time flags** to match RtMidi's real-time-flagged subscription (libmtcmaster's `MtcMaster` and each player's `MtcReceiver` both open with RtMidi). The kernel `match_subs_info` only EBUSY-dedupes when flags match: a PLAIN request from midi-connector plus RtMidi's flagged one → **no dedupe → doubled subscription → doubled MTC quarter-frames (200/s)** → dmxplayer's `isTimecodeActive()` never fires → DMX dead. `connector.py` `_connect` passes `time_update/time_real` **positionally** (pyalsa `connect_ports` is native/positional-only; arg order `src,dst,queue,exclusive,time_update,time_real`); only the `to_through` path uses `(...,0,0,1,1)`. See the dmxplayer CLAUDE.md for the full failure mode.
- **Defer `from_through` wiring at cold boot** to avoid racing a player's own `openPort`. midi-connector wiring `14:0 → player recv` at the same instant the player self-subscribes gives the player EBUSY → RtMidi throws → the player dies (node-engine doesn't respawn). Fix (`9af92bb`): defer the `from_through` wire by a grace period, scoped to the **new-client announce path only** (`process_connections(..., defer_from_through=True)` for `new_client`; `port_unsubscribed` re-wire + startup scan stay immediate — deferring those would add an MTC gap on a runtime link drop). Grace is env-tunable `CUEMS_MIDICONN_FROM_THROUGH_GRACE_S` (default 1.0, mirrors dmxplayer's `CUEMS_DMX_MIDI_WAIT_S`).
- It explicitly **skips `MtcMaster`** ("no pattern match for client 'RtMidiIn Client'"): it only wires `14:0→128:0` to rtpmidid; the MtcMaster→MidiThrough link is made by libmtcmaster itself.
