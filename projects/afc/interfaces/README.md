# interfaces/ — afc 模块接口

| 目录 | 用途 |
|------|------|
| `vehicle_gateway/` | EgoMotion · Perception_In_St · Trajectory |
| `fcm_perception/` | In/Init 粗端口 + **Out 金样** `Perception_Out_messages.h` |
| `planning_driving/` | Trajectory（planning Provide） |
| `demo_fidl/` | Franca 样例（gf-config「导入 fidl…」/ parse_fidl·fdepl 单测） |
| `perception_front/` | **废弃**：旧 FrontObjectList 草稿，主链不再使用 |

由 `cfg/wiring.yaml` 的 `modules[].hpp` 引用。
