# Giraffe_Modules (text layout draft)

> **On-board middleware**: how `sm` / `phm` / `exec` / `com` … boot and collaborate.  
> This is **not** Giraffe_Flow (CARLA / Foxglove / GMT ↔ board).  
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

  ┌──────────┐         ┌─────────────┐         ┌─────────────────────────────┐
  │systemd/  │ ──────► │     EM      │ ──────► │ daemons (via gf-config)     │
  │init dash │         │ gf_em_daemon│         │ · dlt-daemon?               │
  └──────────┘         │   · entry   │         │ · RouDi? (iceoryx)          │
                       └──────┬──────┘         │ · SOME/IP daemon?           │
                              │ OSAL Spawn     │ · DDS?                      │
                              ▼                └─────────────────────────────┘
                       ┌────────────┐
                       │  SOA apps  │
                       └──────┬─────┘
                              │ runtime bring-up
                              ▼
┌──────────────────────────────────────────────────────────────┐
│              In-process middleware ring (main subject)       │
│     exec · phm · sm · collector · per · com · bindings · … │
│     log → DLT  ·  tsync  ·  OSAL                             │
└──────────────────────────────────────────────────────────────┘
```

---

## Module cards (boot)

| Module | One-liner |
|--------|-----------|
| **systemd/init** | OS protection; single unit starts EM only |
| **EM** | Entry: spawn platform daemons + SOA apps per config |
| **daemons (via gf-config)** | dlt / RouDi / SOME/IP / DDS? — enabled via gf-config |

Regen: `python3 result_pic/Giraffe_Modules/scripts/render_gif.py --en`
