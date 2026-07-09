# platform/

| Dir | Role |
|-----|------|
| [osal/](osal/) | OS abstraction — **Linux first**, arch backends **arm** (P0), **mips** / **riscv** (reserved) |
| [hal/](hal/) | Sensors / actuators / `hal/boards/<board>` |

Porting: touch OSAL arch + HAL + deploy profile — **not** business apps.

Build: `-DGF_OSAL_ARCH=arm|mips|riscv`

Parent: [DESIGN.md](../docs/en/architecture/DESIGN.md) § portability
