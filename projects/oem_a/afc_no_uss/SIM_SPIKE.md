# P3-5 Sim spike — `afc_no_uss`

桌面闭环：**契约冻结 → 相机 NV12 → 单管 Foxglove → CARLA Ego/cmd → carla_scenarios truth → 带帧回灌**。  
SKU 文档：[docs/](./docs/) → `docs/zh/sku/afc_no_uss/`（含 [职责说明](./docs/frame_ingest_roles.md)）。

## 主验收路径（完整产品）

```text
起 CARLA UE
→ python3 carla_scenarios/cases/longitudinal/acc.py   # pygame + truth（hero/lead）
→ gf-config: bridge on, ego_source=carla → compile → run_sil
     （bridge 挂 hero，写 YUV 帧 → FCM；cmd thr/brk → 车）
→ Foxglove：BEV + 相机；pygame/CARLA：跟车效果
```

- **bridge 必须**（相对 FCM）：无图像帧则无完整前视产品路径。  
- **无** SKU 冻结的 `dry_run` / `demo_lane_change`（剧情在 `carla_scenarios/`；开发相机自检见 `smoke_carla_sil.sh`）。

## 目录

| 路径 | 跟谁 | 内容 |
|------|------|------|
| `samples/` | 本 SKU | inject×3、stage |
| `carla_scenarios/` | 产品类型 | acc/aeb + CI |
| `docs` → 中央文档 | — | 说明与后续计划 |

## 后续计划（待讨论）

1. **inject 仅跑 planning**（无 FCM / 无图像）与完整产品路径如何并存。  
2. frame_ingest UI 继续去掉「配 FCM」心智（`frame_source` / `perception_backend`）。
