# ADAS demo scenarios（阶段 0）

**推荐合场景：** `overtake_acc_aeb.jsonl` — 双车道超车变道 → ACC 跟车 → 拥堵 AEB。

| 文件 | 说明 |
|------|------|
| **`overtake_acc_aeb.jsonl`** | **主 demo**（约 75s） |
| `acc_follow.jsonl` / `aeb_cutin.jsonl` / `lane_change.jsonl` | 单段片段（调试用） |

`AdasDemo` 是 JSONL 里的可观测 topic，**不是**新的 iceoryx app。

## BEV 从哪来？

**主路径（SIL / 回灌）：** Foxglove bridge 用 **模块输出** 合成俯视图：

`EgoMotion` + `Trajectory` → `/gf/camera/front/compressed`

三幕戏（变道→ACC→AEB）来自同场景 JSONL 里的剧本帧，经 `--bev-script` **只画进 Image**，**不再**向 Studio 发布 `/gf/AdasDemo`。

`run_sil` 默认 `GF_SYNTH_BEV=1`，并自动带上 `scenarios/overtake_acc_aeb.jsonl` 作 bev-script（`GF_BEV_SCRIPT=0` 可关）。

| 模式 | 用法 |
|------|------|
| **playhead（场景 demo）** | `GF_INJECT_MODE=playhead GF_INJECT_LIVE=all bash …/run_sil.sh` → GMT 打开 jsonl 回灌。Studio 看 Ego/Trajectory/**BEV（含相位条/前车/变道）**。 |
| **continuous** | `GF_INJECT_MODE=continuous GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl run_sil` |

GMT **变量轨**仍可读本地 jsonl 里的 AdasDemo（若打开了文件）；Foxglove topic 列表里不应再出现 `/gf/AdasDemo`。

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
