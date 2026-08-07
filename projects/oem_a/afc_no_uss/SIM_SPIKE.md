# P3-5 Sim spike — `afc_no_uss`

桌面闭环：**A（SIL）→ B（帧摄入）→ C（CARLA/dry-run + Foxglove）**。  
配置策略见 [CONFIG_RUNTIME_POLICY.md](../../../docs/zh/operations/CONFIG_RUNTIME_POLICY.md)。

## 主验收路径（推荐）

```text
gf-config 打开本工程 → 页 1「帧摄入 frame_ingest」
  （默认 C dry-run：carla_file + bridge + dry_run）
→ Save / Verify（compose）
→ bash projects/oem_a/afc_no_uss/scripts/compile_sil.sh
→ bash projects/oem_a/afc_no_uss/scripts/run_sil.sh
→ Foxglove Studio → ws://127.0.0.1:8765
```

行为来自 **编译冻结**（`gf_gen/frame_ingest_config.hpp`），**不是**运行期 tip JSON / `.env`。  
手改 `req.yaml` 仅工具底层存盘；请用 gf-config。

## 拓扑

```text
gateway --Perception_In_St--> fcm --Perception_MESSAGE_Out_St--> planning
gateway --EgoMotion----------> planning
planning --Trajectory--------> gateway
                 \--cmd path--> carla_bridge --force_lane_change--> CARLA
CARLA/dry-run --RGB协议--> fcm
```

## frame_ingest（SKU 行为）

| 字段 | 含义 |
|------|------|
| `frame_source` | `none` / `synth` / `file` / `carla_file` |
| `perception_backend` | `stub` / `onnx` |
| `bridge.enabled` | run_sil 是否起 bridge |
| `bridge.dry_run` | 无 UE 写合成帧 |
| `bridge.demo_lane_change` | gateway 定时强制变道 |
| `paths.frame` / `paths.cmd` | 帧协议与 cmd 路径 |

真 CARLA：gf-config 取消 dry_run → Verify → compile → `run_sil`（`CARLA_HOST` 可覆盖部署主机）。

## 调试 env（非验收主路径）

`GF_FRAME_SOURCE` / `GF_START_CARLA_BRIDGE` / … 可临时覆盖冻结值；改 SKU 行为请走 gf-config。

## 薄包装（可选）

`smoke_sil.sh` / `smoke_frame_sil.sh` / `smoke_carla_sil.sh` / `run_carla_sil.sh` 仍可用作超时 grep；**主路径是 `run_sil.sh`**。

## Wave E — AM62（最后）

同一 `frame_ingest` 契约；生产者换成板端 ISP。文档占位，真板后做。
