# someip

**P1 staged** COVESA vsomeip binding — linkable **stub** today (no Boost download).

| API | Behavior |
|-----|----------|
| `InitRuntime` / `Shutdown` | Process-local flag |
| `BackendName()` | `"stub"` (later `"vsomeip"`) |

`.fdepl` SOME/IP IDs: `gf_codegen.compose.parse_fdepl`（**不**代替 `req.bindings`）。样例：`projects/afc/interfaces/demo_fidl/VehicleStatus.fdepl`。

```bash
# CycloneDDS path: scripts/smoke_bd_cyclone.sh
```

Parent: [bindings/README.md](../README.md) · Deps: [dep-manifest/DEPENDENCIES.yaml](../../../dep-manifest/DEPENDENCIES.yaml)
