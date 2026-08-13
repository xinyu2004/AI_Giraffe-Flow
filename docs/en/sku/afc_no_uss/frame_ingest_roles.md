# frame_ingest / bridge / scenarios roles

## Full front-camera product path

`carla_bridge` is **required** relative to FCM: without an image tip, FCM cannot run the product path.  
`frame_ingest.bridge.enabled` starts that tip writer (ISP stand-in for SIL).

| Role | Owns | Does not own |
|------|------|----------------|
| **frame_ingest** | Tip socket: format, paths, ego_source, start bridge | pygame, ACC story, lane scripts, FCM internals |
| **carla_bridge** | Camera→YUV tip, ego tip, apply cmd (CARLA **Python client**) | World story, pygame HMI, functional truth |
| **carla_scenarios/cases/** | World + pygame + truth tip (also a CARLA **client**) | Does not write FCM tip (bridge does) |
| **CARLA UE** | Simulation **server** (RPC `:2000`) | — |
| **manual_control.py** | CARLA human driving UI | Not a Giraffe product component |
| **Foxglove** | Product visualization | Not the CARLA window |

### Client / server (HIL often two hosts)

| Role | What | Typical host |
|------|------|----------------|
| **Server** | CARLA **UE** | Windows sim PC |
| **Client A** | `carla_scenarios/cases/**/*.py` | Often same machine as UE |
| **Client B** | SIL `frame_ingest` → `carla_bridge` | Linux SIL |

Both Python sides are clients to one UE. Each host has its own `carla.env`.

```text
Windows:  carla_scenarios/carla.env  → acc.py ──RPC──┐
                                                   ├→ UE :2000 (server)
Linux:    projects/<sku>/carla.env → run_sil → bridge ─┘
          tip file is local on SIL → FCM
```

- **`run_sil.sh` auto-loads** SKU `carla.env` when starting the bridge (no `enable_*.sh`).
- Do **not** copy scenario `CARLA_HOST=127.0.0.1` onto the SIL.

## Removed from SKU freeze

- `bridge.dry_run` — meaningless on the full-CARLA product path (dev tip smoke: bridge CLI/env only).
- `bridge.demo_lane_change*` — world maneuvers belong in `carla_scenarios/`.

## Two `carla.env` files

| File | Reader | Repo |
|------|--------|------|
| `carla_scenarios/carla.env` | scenario / `run_cases` | tracked (default `127.0.0.1`) |
| `projects/oem_a/afc_no_uss/carla.env` | `run_sil` → bridge | gitignored; copy from `carla.env.example` |

On connect both sides print:

```text
===
carla API  client=…  server=…
===
```

### CI / batch cases

```powershell
python carla_scenarios\run_cases.py
```

```bash
cp projects/oem_a/afc_no_uss/carla.env.example projects/oem_a/afc_no_uss/carla.env
./projects/oem_a/afc_no_uss/scripts/run_sil.sh
```

Default is **live CARLA**. Tip-only CI: `--dry-run`. Scenario lifecycle is independent of SIL.

## Backlog

- **HIL dual-client latency** (after path is proven): SHM tip / fewer RPC / adaptive timeouts; for now `GF_CARLA_BRIDGE_ON_FAIL=reconnect` keeps tip→FCM alive across scenario switches.
- Inject-only planning (no FCM / no images).
- Further UI cleanup: stop exposing FCM-shaped `frame_source` / `perception_backend` knobs.
