# fcm_perception 接口

| 文件 | 角色 |
|------|------|
| [io_ports.hpp](./io_ports.hpp) | `Perception_In_St` / `Perception_Init_St`（粗；In 金样依赖 CamCalib 未入库） |
| [Perception_Out_messages.h](./Perception_Out_messages.h) | **Out 金样** → `Perception_MESSAGE_Out_St`（gf-config / compose 导入） |

wiring `perception.fcm.hpp` 为上述两文件列表。根目录 `100_dbc/` 仅为本地拷贝源，本 SKU 以本目录为准。
