# dep-manifest — dependency pins (managed)

Install: `bash scripts/bootstrap_deps.sh` (wrapper) or `bash dep-manifest/bootstrap.sh`.

This directory is the **pin/manifest** only. Checkouts live under `middleware/third_party/`.

Third-party libraries are **declared and version-pinned here**, not scattered in random READMEs.

| File | Purpose |
|------|---------|
| [DEPENDENCIES.yaml](DEPENDENCIES.yaml) | Canonical dependency list (runtime / tools / optional) |
| [versions.lock.md](versions.lock.md) | Human-readable pin table + upgrade notes |
| [fetch.cmake.in](fetch.cmake.in) | Template for CMake FetchContent (wired later) |
| [CONTRIBUTING_DEPS.md](CONTRIBUTING_DEPS.md) | How to add / bump / vendor a dependency |

Vendor checkout / generated source trees go under [`middleware/third_party/`](../middleware/third_party/) (attr/acl staging: `middleware/.deps-prefix/`). This directory remains the **source of truth for “what we depend on”**.

Documentation: [docs/en/dependencies](../docs/en/dependencies/README.md) · [docs/zh/dependencies](../docs/zh/dependencies/README.md)
