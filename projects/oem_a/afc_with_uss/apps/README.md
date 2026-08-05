# afc_with_uss apps (SKU stubs)

Per-SKU SIL stubs for this product. Process bring-up is [`middleware/runtime/`](../../../../middleware/runtime/) (`gf_ara::runtime`).

| Path | Process |
|------|---------|
| `adapters/vehicle_can_gateway` | `adapter.vehicle_can_gateway` |
| `perception/fcm` | `perception.fcm` |
| `sensing/uss` | `sensing.uss` |
| `planning/driving` | `planning.driving` |

`req.apps` still uses short ids (`adapters/vehicle_can_gateway`, …). CMake resolves them via `GF_PROJECT_DIR` → `projects/.../apps/` first, then shared `apps/`.
