# middleware/

Board-deployable runtime packages. Public headers will use `gf_ara::*`; internals `gf::*`.

| Package | ARA-inspired role | Status |
|---------|-------------------|--------|
| [core](core/) | Result / ErrorCode / Future | skeleton |
| [exec](exec/) | Execution management | skeleton |
| [phm](phm/) | Platform health | skeleton |
| [sm](sm/) | State management | skeleton |
| [com](com/) | Unified communication API | skeleton |
| [log](log/) | Logging | skeleton |
| [trace](trace/) | Trace → VCD/GTKWave hooks | skeleton |

No CMake library targets yet.
