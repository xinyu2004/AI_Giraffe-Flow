# projects/ — 按 OEM / 产品组织的集成工程

每个子目录 = 一个交付项目（系统工程师 + DevOps）。  
**DBC、hpp、wiring、req 全部在本项目内**（无顶层共享目录）。

## 先读

| 文档 | 内容 |
|------|------|
| [PROCESS_ROLES.md](PROCESS_ROLES.md) | 谁是 SOA App / Adapter / 平台 |
| [MODULE_INTERFACE_LAYOUT.md](MODULE_INTERFACE_LAYOUT.md) | 接口与 DBC 均跟项目走 |
| [oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md](oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md) | 第一版集成走查 |
| [UPLOAD_CHECKLIST.md](UPLOAD_CHECKLIST.md) | 上传清单与下一步入口 |
| [../tools/codegen/README.md](../tools/codegen/README.md) | gf-codegen 用法（Python≥3.10） |

## 当前三个项目

| 路径 | OEM | 产品 | 说明 |
|------|-----|------|------|
| [oem_a/afc_no_uss](oem_a/afc_no_uss/) | A | **AFC** | 前视，无 USS |
| [oem_a/afc_with_uss](oem_a/afc_with_uss/) | A | **AFC** | 前视 + 独立 USS（推荐先走查；含 [Golden 说明](oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md#3-golden对照用的正确答案sor)） |
| [oem_b/adc_full](oem_b/adc_full/) | B | **ADC** | 行泊一体；含 [golden/](oem_b/adc_full/golden/) 主示范 |

```text
projects/<oem>/<product>/
  project.yaml  req.yaml  oem/  interfaces/  integration/
  scripts/         # 仅四入口：compile_sil|hil + run_sil|hil（验证 → scripts/verify/）
  reports/  [golden/]
```

**`req.yaml` 跟车型走：** SKU 契约（binding、runtime、acceptance）与部署裁剪（observability、apps）写在同一文件。SIL/HIL 只换编译与运行脚本。改款复制整个产品目录。
