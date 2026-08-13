# carla_bridge — tip writer（afc_no_uss）

Required on the **full front-camera product path**: camera → configured
`pixel_format` tip, ego tip, apply gateway cmd. Stand-in for ISP in SIL.

World / ACC / lane stories: repo `carla_scenarios/` — not this process.  
Human pygame: CARLA `manual_control.py` — optional, not Giraffe.

This process is a CARLA Python **client** (UE is the **server**).  
`run_sil.sh` auto-loads SKU `carla.env` (copy from `carla.env.example`).  
Scenario machine uses `carla_scenarios/carla.env` — do not mix `CARLA_HOST`.

Tip mount geometry: canonical `carla_scenarios/src/lib/_tip_mount.py`; local
`tip_mount.py` only re-exports (set `GF_SCENARIOS_DIR` if the suite is not at
repo-root `carla_scenarios/`).

## Env

| Variable | Default | Meaning |
|----------|---------|---------|
| `GF_CARLA_PYTHON` | auto / `python3` | Interpreter that has `import carla` (conda `carla_env` etc.) |
| `CARLA_HOST` / `CARLA_PORT` | `127.0.0.1` / `2000` | UE RPC (Windows IP when SIL is remote) |
| `GF_PIXEL_FORMAT` | `nv12` | Tip format |
| `GF_CARLA_FRAME_PATH` | `/tmp/gf_front.yuv` | Neutral tip path |
| `GF_CARLA_CMD_PATH` | `/tmp/gf_carla_cmd.json` | Vehicle cmd |
| `GF_CARLA_EGO_PATH` | `/tmp/gf_carla_ego.json` | Ego tip |
| `GF_CARLA_BRIDGE_DRY_RUN` | `0` | **Dev only** (not SKU freeze): synth tip without UE |
| `GF_CARLA_BRIDGE_ON_FAIL` | `reconnect` | `reconnect` keep tip alive; `idle` wait without frames; `exit` old CI behavior |
| `GF_CARLA_RECONNECT_S` | `2` | Backoff between connect / re-session attempts |
| `GF_CARLA_CONNECT_TIMEOUT_S` | `3` | Per RPC timeout (raise for remote HIL, e.g. `10`) |
| `--dry-run` | off | Same as dry-run env (CLI) |

HIL: remote UE + two clients on the **same** RPC port. Bridge **does not spawn**
hero/lead — waits for scenario `role_name=hero`, then attaches tip cam and applies
Giraffe cmd only (scheme-1). Prefer `run_cases.py` (long-lived) so ego is not
destroyed every case. FPS: log `fps carla=… tip_write=…` and `/tmp/gf_carla_bridge_stats.json`
(consumed by `run_sil` heartbeat with tip_read / fcm_read).
Not systemd — child of `run_sil` only (EM is the systemd exception).

### `carla Python module not installed`

`pip install carla` only affects the **active** env. `run_sil` may still call system
`/usr/bin/python3`. Fix:

```bash
export GF_CARLA_PYTHON="$HOME/miniconda3/envs/carla_env/bin/python"
# or: conda activate carla_env   # then re-run run_sil from that shell
export CARLA_HOST=100.98.153.2   # Windows UE Tailscale/LAN — not SIL's own IP
./scripts/run_sil.sh
```

### API versions

On connect, bridge and scenarios print the same banner — compare client vs server:

```text
===
carla API  client=0.9.16  server=0.9.16
===
```

Product SKU freeze has **no** dry_run / demo_lane_change fields.
