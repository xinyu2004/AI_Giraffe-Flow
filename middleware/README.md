# middleware/

Board-deployable packages. Public API: `gf_ara::*`; internals: `gf::*`.

Enable subsets per SKU via SOR `product_variants[].runtime_modules[]`.

| Package | Role | Phase |
|---------|------|-------|
| [core](core/) | Result / ErrorCode | P0 |
| [com](com/) | Unified communication API | P0 |
| [bindings/](bindings/) | Transport plugins (iceoryx / someip / dds …) | P0+ |
| [osal/](osal/) | OS abstraction (clock / thread / **process**) | P0 |
| [hal/](hal/) | Board sensors / actuators | P1+ |
| [third_party/](third_party/) | Upstream checkouts (gitignored) | P0+ |
| [exec](exec/) | ExecutionClient + **EmDaemon** (OSAL Spawn) | P3 |
| [phm](phm/) | Platform health (`notify_sm` / restart→EM) | P3 |
| [sm](sm/) | Function groups Off/Running/Updating | P3 |
| [collector](collector/) | Event collector (DEM-lite / cp_dem stub) | P3 |
| [log](log/) | Logging | P0–P1 |
| [trace](trace/) | Trace → VCD / GMT | P2 |
| [ucm](ucm/) | OTA / packages | P1 skeleton |
| [diag](diag/) | DoIP / UDS types | P1 skeleton |

Staging (gitignored): `middleware/.deps-prefix/` after `bash scripts/bootstrap_deps.sh`.

```bash
bash scripts/bootstrap_deps.sh
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure
# fusa (L1 CASE lines → fusa/runs/):
bash fusa/scripts/run_cases.sh
```

FuSa matrices: [fusa/cases/](../fusa/cases/) · policy: [fusa/POLICY.md](../fusa/POLICY.md).

Unit / component smokes live under each module’s **`testcases/`** directory.
