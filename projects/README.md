# projects/ — 按产品组织的集成工程

每个子目录 = 一个交付项目（系统工程师 + DevOps）。  
**DBC、hpp、wiring、req 全部在本项目内**（无顶层共享目录、无 OEM 层）。

## 先读

| 文档 | 内容 |
|------|------|
| [PROCESS_ROLES.md](PROCESS_ROLES.md) | 谁是 SOA App / Adapter / 平台 |
| [MODULE_INTERFACE_LAYOUT.md](MODULE_INTERFACE_LAYOUT.md) | 接口与 DBC 均跟项目走 |
| [SKU_LAYOUT_TARGET.md](SKU_LAYOUT_TARGET.md) | 现行：仅 `afc` / `adc` |
| [../octave_planning/README.md](../octave_planning/README.md) | Octave `.m` 金源（仅脚本） |
| [../tools/gf-octavecoder/README.md](../tools/gf-octavecoder/README.md) | octavecoder + `gf_octave_planning` → `oct_gen/` → `gf_planning_driving` |
| [afc/RUNTIME_FOOTPRINT.md](afc/RUNTIME_FOOTPRINT.md) | runtime 体积：产品 ~5M vs obs 膨胀 |
| [afc/README.md](afc/README.md) | AFC 集成入口与验收 |
| [UPLOAD_CHECKLIST.md](UPLOAD_CHECKLIST.md) | 上传清单与下一步入口 |
| [../tools/gf-codegen/README.md](../tools/gf-codegen/README.md) | gf-codegen 用法（Python≥3.10） |

## 当前项目

| 路径 | 产品 | 说明 |
|------|------|------|
| [afc](afc/) | **AFC** | 前视，无 USS |
| [adc](adc/) | **ADC** | 行泊一体；含 [golden/](adc/golden/) 主示范 |

```text
projects/<sku>/
  project.yaml  req.yaml  oem/  interfaces/  integration/
  scripts/         # 四入口 compile|run × sil|hil；验收 smoke → scripts/verify/
  reports/         # lineage、iox_shm_report 等（非 generated；本地生成）
  [golden/]
```

**`req.yaml` 跟车型走：** SKU 契约（binding、runtime、acceptance）与部署裁剪（observability、apps）写在同一文件。SIL/HIL 只换编译与运行脚本。改款复制整个产品目录。
