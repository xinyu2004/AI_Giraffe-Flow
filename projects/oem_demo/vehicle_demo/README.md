# oem_demo / vehicle_demo — 集成工程示例

系统工程师工作区。换 OEM / 新车型的做法：**复制本目录**到 `projects/<oem>/<vehicle>/`，改四类输入即可。

## 四类输入 + 一个入口

| 文件 | 职责 |
|------|------|
| 各模块仓 **`io_types.hpp`** | 模块工程师：数据形状（路径在 `integration/wiring.yaml` 登记） |
| **`oem/oem_import.dbc`** | OEM 车身信号（每车型可不同） |
| **`integration/wiring.yaml`** | 信号连线、provide/require、dataflow |
| **`req.yaml`** | SKU、能力、部署 profile、**DevOps 验收项** |
| **`project.yaml`** | **仅索引**以上路径 + 输出 SOR；不含业务细节 |

## 一句话 compose（P1 实现）

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```

产出：`gf.sor.json` + `reports/signal_lineage_report.yaml`

## DevOps

`req.yaml` 的 `acceptance` 段声明 golden SOR、必选服务、lineage 是否必须通过 — CI 据此判定交付是否满足客户配置。

Golden 参考：[Requirement/vehicle_demo.sor.json](../../Requirement/vehicle_demo.sor.json)
