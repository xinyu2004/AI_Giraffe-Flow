# middleware/

Board-deployable packages. Public API: `gf_ara::*`; internals: `gf::*`.

Enable subsets per SKU via SOR `product_variants[].runtime_modules[]`.

| Package | ARA role | Phase |
|---------|----------|-------|
| [core](core/) | Result / ErrorCode / Future | P0 |
| [com](com/) | Unified communication | P0 |
| [exec](exec/) | Execution management | P1 |
| [phm](phm/) | Platform health | P1 |
| [sm](sm/) | State management | P1 |
| [log](log/) | Logging | P0–P1 |
| [trace](trace/) | Trace → VCD / GMT | P2 |
| [ucm](ucm/) | OTA / packages (`gf_ara::ucm`) | P1 skeleton |
| [diag](diag/) | DoIP / UDS types (`gf_ara::diag`) | P1 skeleton |

No CMake targets yet — see [ROADMAP](../docs/en/operations/ROADMAP.md).
