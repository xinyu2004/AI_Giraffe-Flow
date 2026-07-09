# OS abstraction layer

| Path | Role |
|------|------|
| `include/gf/osal/` | Public API (P0) |
| `src/posix/` | Linux pthread, clocks, shm |
| [arch/](arch/) | **arm** (P0), **mips**, **riscv** reserved |

CMake: `-DGF_OSAL_ARCH=arm|mips|riscv`

Parent: [platform/README.md](../README.md)
