# projects/ — 按客户 / 车型组织的集成工程

每个子目录 = 一个**实际交付项目**（系统工程师 + DevOps 的主战场）。

```text
projects/
  <oem>/
    <vehicle>/
      project.yaml           # compose 入口（索引，非替代四类文件）
      req.yaml               # SKU / 部署 / 验收
      oem/
        oem_import.dbc
        oem_import.yaml
        dbc_vehicle_can.extract.yaml   # 可选 review
      integration/
        wiring.yaml
      reports/                 # lineage 输出（CI 产物）
```

示例：[oem_demo/vehicle_demo/](oem_demo/vehicle_demo/)

模块 `io_types.hpp` 通常在各模块仓；在 `wiring.yaml` 的 `modules[].hpp` 登记路径。

平台归档与 golden：[Requirement/](../Requirement/)

文档：[docs/zh/architecture/sor-authoring.md](../docs/zh/architecture/sor-authoring.md)
