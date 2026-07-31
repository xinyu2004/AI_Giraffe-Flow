# sm — Function Group state machine (M1 minimal)

| API | Role |
|-----|------|
| `StateClient::EnsureGroup` | Register FG + initial state |
| `RequestTransition` | Off ↔ Running ↔ Updating |
| `NotifyHealthFault` | PHM hook (M2); optional enter Updating |
| `GetState` / `FaultCount` | Query |

In-process only (SIL). Not a full AUTOSAR SM daemon.

Smoke: `gf_sm_fg_smoke`（`testcases/smoke_fg.cpp`）。Trust cases: [sm_cases.md](../../docs/reports/trust-evidence/sm_cases.md)。

Parent: [middleware/README.md](../README.md)
