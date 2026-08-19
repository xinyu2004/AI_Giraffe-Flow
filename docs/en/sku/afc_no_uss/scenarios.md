# Product scenarios (`carla_scenarios`)

CARLA **Client A**: place + IC; continuous ego control is Giraffe→bridge only.
Implementation lives under `carla_scenarios/src/`.

```text
carla_scenarios/
  README.md          # links here (zh/en)
  run_cases.py       # ★ batch entry → results/runs/<timestamp>/
  carla.env          # defaults (duration, …; CLI may override)
  manifest.yaml
  cases/
  results/           # batch only (single-case scripts do not write)
  src/
    spawn/           # pick / place / ic / boundary / roles
    layouts/         # layout families (≠ product domain dirs under cases/)
    lib/             # AtomCase, view, verdict, carla_env…
    judges/
    cluster_templates/
```

## Architecture snapshot (Client A)

| Layer | Path | One line |
|-------|------|----------|
| Product list | `cases/**/manifest.yaml` | id/script/status/keyword only — no layout/spawn fields |
| Thin cases | `cases/**/*.py` | AtomCase binds layout + judge + on_tick |
| Layouts | `src/layouts/*` | explicit `pick → place → named ic` |
| Bricks | `src/spawn/{pick,place,ic,boundary,roles}` | pick / place-at-rest / case IC / inter-case sanitize / roles |
| Batch | `run_cases.py` | long-lived client; `sanitize_keep_ego` between cases |
| Gate | `scripts/check_spawn_import_gate.sh` | import isolation |

scheme-1: **scenario = place + IC only**; continuous control is Giraffe→bridge. Without SIL, place still runs; verdict is often `no_giraffe_control` (verdict only — not mid-run AEB braking).

## Spawn layering (manifest has no code hooks)

**Rule:** `manifest.yaml` lists product metadata only (id / script / status / keyword / tags / description). It never names layout / spawn / judge / import. Case → code is only via `script:`; the script imports its layout.

### Brick responsibilities

| Module | Allowed | Forbidden |
|--------|---------|-----------|
| `src/spawn/pick.py` | return transforms | actors, speed, keep_ego |
| `src/spawn/place.py` | spawn / destroy / clear / retry | constant velocity, case branches, settle+IC |
| `src/spawn/ic.py` | **named** IC profiles | silent calls from place/pick |
| `src/layouts/*` | explicit `pick → place → ic_xxx` | global defaults in `spawn.*`; `if case_id` in shared helpers |

Lifecycle (dynamic decoupling)::

```text
place (pose + at rest) → named case IC → run/judge
        ↑                                  │
        └──── boundary.sanitize_keep_ego ◄─┘  (batch/combo)
```

- **boundary**: sole owner of keep_ego residue; exit `|v|≈0`; on failure **destroy hero**.
- **place**: pose + at-rest only; no const-vel / reverse fixes.
- **case IC**: assumes a clean boundary; no flip / residue rescue.

Named IC:

- `release_only` — ACC / weather follow
- `closing_toward_lead` — vehicle–vehicle AEB/FCW
- `closing_along_heading` — map road forward (VRU ego, same-dir bike)
- `closing_along_pose` — cross-traffic yaw (never for ego)
- `seed_speed` — lateral / env
- collision early-exit: `_verdict.freeze_actors`

`src/lib/_spawn.py` is re-export only.

### Import gate

| Who | May import |
|-----|------------|
| `layouts/closing.py` | `closing_toward_lead` / `closing_along_heading` / `closing_along_pose` |
| `layouts/vru.py` | **`closing_along_heading` only** |
| `layouts/follow_straight.py` | **`release_only` only** |
| other speed IC layouts | `seed_speed` etc. |
| `run_cases.py` | **`spawn.boundary.sanitize_keep_ego` only** |
| `AtomCase` | may `sanitize_keep_ego`; **must not** `spawn.ic` |
| `place` / `pick` | **must not** ic / boundary |

Smoke check:

```bash
cd carla_scenarios && bash scripts/check_spawn_import_gate.sh
```

Batch: static isolation via imports; world residue via `boundary.sanitize_keep_ego`. Combos import only the layout phases they use; phase switches are explicit sanitize + the next phase's IC.

**IC note:** CARLA `enable_constant_velocity` is **vehicle-local** (`(+speed,0,0)` forward). Do not pass world-frame velocity into it (caused ACC→AEB reverse).

### Done this arc / still open

Done: spawn layering + explicit layouts; AtomCase for acc/aeb; boundary sanitize; named IC; import gate; env knobs; collision freeze.

Open (defer; frame_ingest next): no-Giraffe `exit=1` is expected; VRU/cross polish; brake visuals from lead hold / sanitize / freeze ≠ ego AEB; other domains not closed this round.

### Taxonomy moves / add-merge checklist

| Change | Touch | Do not touch |
|--------|-------|--------------|
| Product domain only | move script; two manifests; root suite children if needed | `spawn.*`, layout bodies |
| New atom (same layout) | thin script + manifest row | other cases; pick/place |
| New layout / new IC | new layout ± new `ic.xxx` + case + manifest | old IC defaults; unrelated layouts |
| Merge / split cases | scripts + manifest rows; layout share or fork | spawn core |
| Combo phases | combo script imports / handoff only | atom layout defaults |

**Effort:** add/merge usually small; domain renames mechanical (mv + manifest); physics changes stay in one layout (fork the function if shared).

**Checklist:** (1) product-only move vs layout-family split (2) `mv` + manifests + suite (3) `rg` old paths/symbols (4) leave `spawn/{pick,place,ic}` alone unless physics/IC changes (5) smoke one case + domain batch.

## Run

```bash
cd carla_scenarios
python3 run_cases.py cases/longitudinal
python3 run_cases.py --no-window cases/weather
python3 cases/longitudinal/acc.py          # single case; no results/
```

### Align camera with gf-config

After compose, the SKU writes `generated/camera_contract.json`. Scenarios **read** it (no copy into this tree):

```bash
export GF_PROJECT_DIR=/path/to/projects/oem_a/afc_no_uss
# or: export GF_CAMERA_CONTRACT=$GF_PROJECT_DIR/generated/camera_contract.json
python3 cases/longitudinal/acc.py
```

See [frame_ingest_roles.md](./frame_ingest_roles.md).

- Batch targets are directories with `manifest.yaml` only.  
- Defaults in **`carla.env`** (CLI may override):  
  - `GF_SCENARIO_DURATION_S=8` (most cases)  
  - `GF_SCENARIO_DURATION_ISP_S=25` (tunnel / ISP enter+exit)  
  - `GF_CARLA_TOWN=Town04` (optional load after connect; independent of UE startup map; empty = keep)  
  - `GF_TRAFFIC_DENSITY=1` (TM ambient on all cases; 0=off; batch never wipes between cases, only top-up)  
  - `GF_SCENARIO_WRITE_RESULTS=1` (batch `results/` report; default on; `0` / `--no-results` off)  
- `GF_SCENARIO_STOP_ON_FAIL=0` continue; `=1` / `--stop-on-fail` abort.  
- AEB family: collision early-exit fail.  
- No SIL → `no_giraffe_control` (exit 1); infra → exit 2.

## Results (batch only)

See `carla_scenarios/results/README.md`.

## Instrument cluster

- v3 translucent **top bar + hood band**:  
  - top: `i/N keyword·id` · `t / T s`  
  - band: speed kph · SET · TGT · **template slots** (th/gap, TTC, …) · CTRL  
- Feature plugins: `src/cluster_templates/` (sibling of `lib/` / `layouts/` / `judges/`; unknown → `common`).  
- **CTRL**: green blink with control; red blink without.  
- No CAM / View chrome; keyboard `V` still toggles ChaseCam silently.

## Domains

`longitudinal` · `lateral` · `perception` · `lighting` · `roadway` · `isp_env` · `weather`

## Verdict contract

| Item | Rule |
|------|------|
| scenario | place + IC only |
| ego | Giraffe→bridge only |
| no SIL | fail `no_giraffe_control` |
| exit | `0` pass / `1` fail / `2` infra |

## Still open

- Domain cleanup (glare → `isp_env`); pick scenery by **case coverage**, not fake ties like village↔sun  
- Scene cleanliness = less clutter; ambient traffic is normal (not FPS work)  
- FPS / camera / frame_ingest (separate track)  
- Real SET / lat-offset / HLB beam from planning  
- Richer `results/` verdict fields
