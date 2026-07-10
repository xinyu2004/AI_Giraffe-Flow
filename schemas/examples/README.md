# SOR examples

| File / dir | Topology | Purpose |
|------------|----------|---------|
| [minimal.sor.json](minimal.sor.json) | — | legacy empty stub |
| [desktop_ap_only.sor.json](desktop_ap_only.sor.json) | `ap_only` | simulators |
| [vehicle_ap_mcu_cp.sor.json](vehicle_ap_mcu_cp.sor.json) | `ap_mcu_cp` | MCU CP gateway + DoIP |
| [oem/](oem/) | — | `import oem` fragment（仅 DBC） |
| [modules/](modules/) | — | `synthesize --from-hpp` 模块示例 |
| [projects/oem_b/adc_full/golden/gf.sor.json](../../projects/oem_b/adc_full/golden/gf.sor.json) | `ap_mcu_cp` | **从真实 DBC/xlsx 提炼的 golden** |

Golden tests for `gf-codegen lint` (P0+).  
OEM 导入说明：[docs/zh/architecture/sor-authoring.md](../../docs/zh/architecture/sor-authoring.md)
