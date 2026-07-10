# OS abstraction layer (P0)

Lives under **middleware** (board runtime). Public API: `gf::osal`.

| Path | Role |
|------|------|
| `include/gf/osal/` | `MonotonicNowNs`, `SleepMs` |
| `src/posix/` | Linux POSIX backend |
| [arch/](arch/) | **arm** (P0), **mips**, **riscv** reserved |

```bash
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build --target gf_osal_smoke
./build/middleware/osal/gf_osal_smoke
```

Parent: [../README.md](../README.md)
