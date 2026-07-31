# OS abstraction layer (P0)

Lives under **middleware** (board runtime). Public API: `gf::osal`.

| Path | Role |
|------|------|
| `include/gf/osal/` | `MonotonicNowNs`, `SleepMs`, `SpawnProcess` / `WaitProcess` / `TerminateProcess` / `KillProcess` |
| `src/posix/` | Linux POSIX backend（clock / thread / process） |
| [arch/](arch/) | **arm** (P0), **mips**, **riscv** reserved |

`EmDaemon` 只依赖 process API，不直接调用 `fork`/`exec`。

```bash
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build --target gf_osal_smoke gf_osal_process_smoke
ctest -R 'gf_osal' --output-on-failure
```

Parent: [../README.md](../README.md)

Trust cases: [osal_cases.md](../../docs/reports/trust-evidence/osal_cases.md).
