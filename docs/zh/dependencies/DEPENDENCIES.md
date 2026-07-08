# 外部依赖概览

## 运行时（可能上车）

| 库 | 用途 |
|----|------|
| **iceoryx** | 机内零拷贝（雷达/相机/融合） |
| **vsomeip** | SOME/IP，车规 SOA / ECU |
| **CycloneDDS（+ cxx）** | DDS，对接 ROS 2 / 跨 SoC |
| **nlohmann/json** | SOR 与 manifest |

## 仅主机工具

| 库 | 用途 |
|----|------|
| **yaml-cpp** | `req.yaml` / profile |
| **CLI11** | importer / codegen / lint CLI |
| **GoogleTest** | 单测 |

## 可选 / 延后

| 库 | 说明 |
|----|------|
| **spdlog** | DLT 前的过渡日志 |
| **Boost** | 优先用 BSP；常为 vsomeip 传递依赖 |
| **OpenVX 实现** | 视觉 pipeline；随 SoC 选型 |
| **ROS 2 rclcpp** | 优先 DDS 直连 |
| **DLT / SQLite** | P1+ |

策略：先改 `deps/DEPENDENCIES.yaml` 与 `versions.lock.md`；板端 CI 不得编入主机 GUI / ROS 桌面依赖。
