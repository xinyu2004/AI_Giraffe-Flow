# interfaces/ — afc_no_uss 模块接口

| 目录 | 用途 |
|------|------|
| `vehicle_gateway/` | EgoMotion · Perception_In_St · Trajectory |
| `fcm_perception/` | In/Init 粗端口 + **Out 金样** `Perception_Out_messages.h` |

| `planning_driving/` | Trajectory（planning Provide） |
| `perception_front/` | **废弃**：旧 FrontObjectList 草稿，主链不再使用 |

由 `integration/wiring.yaml` 的 `modules[].hpp` 引用。
