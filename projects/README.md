# projects/ — 按 OEM / 产品组织的集成工程

每个子目录 = 一个交付项目（系统工程师 + DevOps）。

## 先读：谁是 SOA App？

→ **[PROCESS_ROLES.md](PROCESS_ROLES.md)**（Adapter / SOA App / 平台 daemon 分类）

## 当前三个项目

| 路径 | OEM | 产品 | 说明 |
|------|-----|------|------|
| [oem_a/afc_no_uss](oem_a/afc_no_uss/) | A | **AFC** | 前视，无 USS |
| [oem_a/afc_with_uss](oem_a/afc_with_uss/) | A | **AFC** | 前视 + 独立 USS |
| [oem_b/adc_full](oem_b/adc_full/) | B | **ADC** | 行泊一体（前视/环视/USS/规划/MCU） |

```text
projects/
  oem_a/
    afc_no_uss/
    afc_with_uss/
  oem_b/
    adc_full/
  oem_demo/vehicle_demo/   # 旧对照样例，新工作以上面三个为准
  PROCESS_ROLES.md
```

每个项目内：

```text
project.yaml / req.yaml / oem/ / integration/wiring.yaml / reports/
```

模块 hpp 示例：[Requirement/modules/](../Requirement/modules/)  
文档：[sor-authoring.md](../docs/zh/architecture/sor-authoring.md)
