# interfaces/ — 本项目模块接口（hpp / fidl）

外仓常只交 `io_types.hpp` 或 Franca `.fidl`；落在本目录，由 `integration/wiring.yaml` 的 `modules[].hpp` / `modules[].fidl` 引用。  
DBC 在 `oem/`。顶层 `Requirement/` 已删除，无共享双轨。

样例 FIDL：`demo_fidl/VehicleStatus.fidl`（可用 gf-config B 页「导入 fidl…」试跑）。

见 [MODULE_INTERFACE_LAYOUT.md](../../MODULE_INTERFACE_LAYOUT.md)
