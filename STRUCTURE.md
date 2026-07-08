# Repository layout

This monorepo is a **skeleton only** (no runtime/tool implementation yet).

```text
AI_Giraffe-Flow/
  schemas/          # SOR contract (gf.sor.schema.json) + examples
  middleware/       # On-board runtime packages (core/exec/phm/sm/com/log/trace)
  platform/         # OSAL + HAL
  bindings/         # iceoryx / someip / dds plugins
  bridge/           # Optional ROS2 / protocol bridges
  tools/            # Host-only: importer, codegen, architect, record_replay, lint
  apps/             # Reference processes (not customer production apps)
  deploy/           # profiles + manifests
  deps/             # Dependency manifests & lock policy (managed here)
  third_party/      # Vendored / FetchContent stubs (sources later)
  cmake/            # Shared CMake helpers (later)
  ci/               # CI workflow stubs
  scripts/          # Dev helper scripts (later)
  docs/en|zh/       # Design, workflow, dependency docs
```

See also:

- [README.md](README.md) / [README_zh.md](README_zh.md)
- [docs/en/dependencies/README.md](docs/en/dependencies/README.md)
- [deps/README.md](deps/README.md)
