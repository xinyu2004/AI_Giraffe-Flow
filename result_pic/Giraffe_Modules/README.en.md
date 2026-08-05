# Giraffe_Modules (text layout draft)

> **On-board middleware**: how `sm` / `phm` / `exec` / `com` … boot and collaborate.  
> This is **not** Giraffe_Flow (that diagram is CARLA / Foxglove / GMT ↔ board).  
> Chinese: [`README.md`](./README.md)

| Diagram | Focus |
|---------|--------|
| **Giraffe_Flow** | System data path: externals · config · host tools ↔ board |
| **Giraffe_Modules** | **Inside the board** `middleware/*`: inventory, boot, call graph |

Source: [`middleware/README.md`](../../middleware/README.md)

---

## Proposed full-frame layout (module-centric)

```text
┌──────────────────────────────────────────────────────────────┐
│  TITLE: Giraffe Modules · how middleware boots & collaborates│
└──────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │ iceoryx     │   com dependency (RouDi)
                    │ RouDi       │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ gf_em_daemon│   ← exec / EM
                    │    (EM)     │
                    └──────┬──────┘
                           │ OSAL Spawn (em_launch topo)
                           ▼
              ┌────────────────────────────┐
              │   SOA apps (processes)     │
              │   gateway · sensing · …    │
              └─────────────┬──────────────┘
                            │ per-process: runtime bring-up
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              In-process middleware ring (main subject)       │
│                                                              │
│     exec Client ◄── Offer / Alive ──► phm                    │
│         │                              │                     │
│         │ EnsureGroup                  │ NotifyHealthFault   │
│         └──────────────► sm ◄──────────┘                     │
│                     Off / Running / Updating                 │
│                              │                               │
│                              ▼                               │
│                         collector ──persist──► per           │
│                         (DEM-lite / events)                  │
│                                                              │
│     com ──Proxy/Skeleton──► bindings                         │
│                             (iceoryx | SOME/IP | DDS)        │
│                                                              │
│     diag ──DoIP/UDS──► ucm ──► sm Updating + phm pause       │
│                           └──fail──► collector               │
│                                                              │
│     log          tsync          OSAL (clock/thread/process)  │
└──────────────────────────────────────────────────────────────┘

  FuSa evidence attaches to real behavior of:
  exec / phm / sm / collector …
  (POLICY · cases · metrics · safety-case)
```

---

## Module cards (one card per block when drawing)

### Lifecycle

| Module | One line | Key peers |
|--------|----------|-----------|
| **OSAL** | Clock / thread / **process** Spawn·Wait·Kill | Only EM starts/stops processes via OSAL |
| **exec / EM** | `ExecutionClient` + `gf_em_daemon` | Reads em_launch; topo Spawn; optional relaunch |
| **sm** | Function groups Off ↔ Running ↔ Updating | runtime EnsureGroup; PHM faults; UCM Updating |
| **phm** | Alive / Deadline / Logical | App ReportAlive; on fail → log / collector / sm / EM |
| **runtime** | In-process bring-up glue | log → SM → Exec Offer → PHM Alive → collector hooks |

### Communication & time

| Module | One line | Key peers |
|--------|----------|-----------|
| **com** | Unified Event Proxy/Skeleton | → bindings; apps use service names only |
| **bindings** | iceoryx / SOME/IP / DDS / … | Behind com; needs RouDi etc. |
| **tsync** | Time-sync skeleton | OSAL Now; SKU-trimmable |
| **log** | Lite logging | Bring-up / fault paths |

### Diagnostics · OTA · events · persistency

| Module | One line | Key peers |
|--------|----------|-----------|
| **collector** | Event ring + DEM-lite → DTC | Fed by PHM/UCM; **per** store; **diag** UDS pull |
| **per** | Cross-reboot KV | Collector DTC / versions |
| **diag** | DoIP + UDS | → **ucm** OTA; host GMT is only a client |
| **ucm** | PackageManager + OtaOrchestrator | SM Updating + PHM pause; fail → collector |

### Supporting (small print)

| Module | Note |
|--------|------|
| **core** | Result / ErrorCode; all packages |
| **hal** | Board I/O skeleton (P1+) |
| **trace** | Timing → VCD (debug-path, not ASIL evidence) |

---

## Key call chains (text)

**Health loop**

```text
App ReportAlive → phm Evaluate
    → collector (+ optional per DTC)
    → sm NotifyHealthFault
    and/or exec/EM RequestRestart (or exit 75 relaunch)
```

**OTA window**

```text
DoIP(diag) → ucm OtaOrchestrator
    → sm Updating
    → phm SetPaused
    → on fail → collector
```

**Communication**

```text
App ──service name──► com ──► bindings ──► iceoryx | SOME/IP | DDS
```

---

## Explicitly out of this diagram

- CARLA / Foxglove / GMT / gf-config (→ **Giraffe_Flow**)
- OEM algorithm internals, specific test topic names
- Host GUIs, offline MCAP tooling

---

## Drawing notes

1. Hero = middleware ring + EM spawn arrow — do not redraw Flow peripherals.
2. Chip names match Flow SoC strip: `com · EM · exec · phm · sm · collector · OSAL · diag · ucm · log · per · tsync`.
3. Label arrows with actions (Spawn / Alive / NotifyFault / DoIP).
4. Lock ZH layout first; EN follows this file.

Generated:

| | Path |
|--|------|
| ZH GIF / SVG | `Giraffe_Modules.gif` · `Giraffe_Modules.svg` |
| EN GIF / SVG | `Giraffe_Modules.en.gif` · `Giraffe_Modules.en.svg` |

Regen: `python3 result_pic/Giraffe_Modules/scripts/render_gif.py` (add `--en` for English too).
