# platform/

| Dir | Role |
|-----|------|
| [osal/](osal/) | OS abstraction (threads, clocks, shm, processes) — Linux first, QNX later |
| [hal/](hal/) | Sensors / actuators / board packs under `hal/boards/` |

Porting a SoC should touch OSAL + HAL + deploy profile — not business apps.
