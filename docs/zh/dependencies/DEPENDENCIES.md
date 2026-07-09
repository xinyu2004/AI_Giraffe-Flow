# 外部依赖概览

完整评估：[THIRD_PARTY_EVALUATION.md](THIRD_PARTY_EVALUATION.md)

## 运行时（可上车，按 runtime_modules 裁剪）

| 库 | 用途 | 阶段 |
|----|------|------|
| **iceoryx** | 机内零拷贝 | P0 |
| **vsomeip** | SOME/IP | P1 |
| **CycloneDDS（+ idlc）** | DDS / ROS 互操作 | P1 |
| **nlohmann/json** | SOR / manifest | P0 |

## 中间件（自研，非三方）

| 包 | 用途 | 阶段 |
|----|------|------|
| **ucm** | OTA | P1 skeleton |
| **diag** | DoIP | P1 skeleton |

## 主机

| 库 | 用途 |
|----|------|
| **CLI11** | gf-codegen、GMT |
| **cantools** | DBC import |
| **MCAP** | GMT measure |

## OTA 候选（不含 SWUpdate）

RAUC、OSTree — 见 manifest `ota_stack`。

策略：先改 [DEPENDENCIES.yaml](../../deps/DEPENDENCIES.yaml) 与 [versions.lock.md](../../deps/versions.lock.md)。
