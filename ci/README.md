# CI (stubs)

Workflows will live under `workflows/` once the build system exists.

Planned jobs:

| Job | Builds | Notes |
|-----|--------|-------|
| `docs` | — | Link/markdown checks |
| `schemas` | — | Validate examples against `gf.sor.schema.json` |
| `tools-host` | tools/* | Host only |
| `runtime-desktop` | middleware + bindings | x86_64 |
| `runtime-board` | middleware + bindings | cross aarch64; **no** architect GUI |
| `e2e-smoke` | apps demo | Multi-process bring-up |

See [../deps/README.md](../deps/README.md) for dependency policy on board jobs.
