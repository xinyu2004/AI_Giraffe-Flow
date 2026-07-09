# OSAL architecture backends

Linux-first embedded targets. Select backend at build time via `GF_OSAL_ARCH`.

| Backend | Status | Typical triple |
|---------|--------|----------------|
| [arm/](arm/) | **P0 primary** | `aarch64-linux-gnu`, `arm-linux-gnueabihf` |
| [mips/](mips/) | Reserved | `mips-linux-gnu`, `mipsel-linux-gnu` |
| [riscv/](riscv/) | Reserved | `riscv64-linux-gnu` |

Shared POSIX code lives in `../src/posix/`. Arch dirs supply atomics, cache line, optional syscall quirks.

Parent: [osal/README.md](../README.md)
