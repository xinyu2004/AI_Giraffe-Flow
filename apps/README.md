# apps/

Shared demos and adapters for integration tests. SKU **workload** apps (gateway / FCM / planning) live under `projects/<sku>/apps/` — a closed loop to exercise the middleware, not a production ADAS claim.

## Layout（现行）

| Dir | Role |
|-----|------|
| [common/](common/) | Shared demo headers (e.g. `uss_zones_topic`) |
| [adapters/](adapters/) | Shared adapters (e.g. `mcu_cp_gateway`) |
| [simulators/](simulators/) | Semantic output stubs when an OEM package is absent |
| [demo_pipeline/](demo_pipeline/) | End-to-end wiring demo |

SKU 载荷（gateway / FCM / 规划金源）在：

`projects/<oem>/<sku>/apps/`

例：[projects/afc/apps/](../projects/afc/apps/)。

Process bring-up → [`middleware/runtime/`](../middleware/runtime/)。  
Tap / inject / Foxglove WS → [`tools/gmt_board/`](../tools/gmt_board/)。

OEM camera/NN 仍可外仓（SOR `components[].package`）。本仓 AFC 路径用感知+规划当 **载荷**，验证中间件与工具。

Parent: [component-composition.md](../docs/en/architecture/component-composition.md)
