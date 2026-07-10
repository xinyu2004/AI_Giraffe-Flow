# middleware/

Board-deployable packages. Public API: `gf_ara::*`; internals: `gf::*`.

Enable subsets per SKU via SOR `product_variants[].runtime_modules[]`.

| Package | Role | Phase |
|---------|------|-------|
| [core](core/) | Result / ErrorCode | P0 |
| [com](com/) | Unified communication API | P0 |
| [bindings/](bindings/) | Transport plugins (iceoryx / someip / dds …) | P0+ |
| [osal/](osal/) | OS abstraction (clock / thread) | P0 |
| [hal/](hal/) | Board sensors / actuators | P1+ |
| [third_party/](third_party/) | Upstream checkouts (gitignored) | P0+ |
| [exec](exec/) | Execution management | P1 |
| [phm](phm/) | Platform health | P1 |
| [sm](sm/) | State management | P1 |
| [log](log/) | Logging | P0–P1 |
| [trace](trace/) | Trace → VCD / GMT | P2 |
| [ucm](ucm/) | OTA / packages | P1 skeleton |
| [diag](diag/) | DoIP / UDS types | P1 skeleton |

Staging (gitignored): `middleware/.deps-prefix/` after `bash scripts/bootstrap_deps.sh`.

```bash
bash scripts/bootstrap_deps.sh
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build -j"$(nproc)"
```
