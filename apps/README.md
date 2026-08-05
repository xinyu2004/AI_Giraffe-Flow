# apps/

Shared / reference processes for integration tests — **not** customer production algorithms.

## Layout（现行）

| Dir | Role |
|-----|------|
| [common/](common/) | Shared demo headers (e.g. `uss_zones_topic`) |
| [adapters/](adapters/) | Shared adapters (e.g. `mcu_cp_gateway`) |
| [simulators/](simulators/) | Semantic output stubs when external repos absent |
| [demo_pipeline/](demo_pipeline/) | End-to-end wiring demo |

SKU 业务 stub（gateway / uss / fcm / planning）在：

`projects/<oem>/<sku>/apps/`

例：[projects/oem_a/afc_with_uss/apps/](../projects/oem_a/afc_with_uss/apps/)。

Process bring-up → [`middleware/runtime/`](../middleware/runtime/)。  
Tap / inject → [`tools/debug_bridge/`](../tools/debug_bridge/)。

Production perception / planning / control 在外部仓库；SOR `components[].package` 选 sim vs production。

Parent: [component-composition.md](../docs/en/architecture/component-composition.md)
