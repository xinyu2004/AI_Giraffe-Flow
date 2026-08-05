# ADAS demo scenarios（阶段 0）

**推荐合场景：** `overtake_acc_aeb.jsonl` — 双车道超车变道 → ACC 跟车 → 拥堵 AEB。

| 文件 | 说明 |
|------|------|
| **`overtake_acc_aeb.jsonl`** | **主 demo**（约 75s） |
| `acc_follow.jsonl` / `aeb_cutin.jsonl` / `lane_change.jsonl` | 单段片段（调试用） |

`AdasDemo` 是 JSONL 里的可观测 topic，**不是**新的 iceoryx app。

## 谁加载这个 JSONL？

**主路径：GMT / Inject。** `run_sil` **不**挂场景 JSONL。

1. `bash …/run_sil.sh`（默认 `GF_SYNTH_BEV=1`）→ Foxglove 只从 **EgoMotion + Trajectory** 合成 BEV Image  
2. 场景文件二选一：  
   - **playhead**：GMT **打开** `scenarios/overtake_acc_aeb.jsonl` → 连回灌 → 播放  
   - **continuous**：`GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl` 给板端 inject 读文件  

| 模式 | 用法 |
|------|------|
| **playhead（场景 demo）** | `GF_INJECT_MODE=playhead GF_INJECT_LIVE=all bash …/run_sil.sh` → GMT 打开 jsonl 回灌 |
| **continuous** | `GF_INJECT_MODE=continuous GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl run_sil` |

GMT **变量轨**可读本地 jsonl 里的 AdasDemo；Foxglove topic 列表里不应再出现 `/gf/AdasDemo`。

```bash
python scripts/gen_adas_scenarios.py

GF_INJECT_MODE=playhead GF_INJECT_LIVE=all \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# GMT：打开 overtake_acc_aeb.jsonl → 回灌 → 播放
# Studio → ws://…:8765 → Image /gf/camera/front/compressed + Plot EgoMotion/Trajectory

# 离线（无 SIL）也可：同样合成 BEV，且不广告 AdasDemo topic
GMT bridge foxglove --ws --synth-bev \
  --jsonl projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl --port 8765
```
