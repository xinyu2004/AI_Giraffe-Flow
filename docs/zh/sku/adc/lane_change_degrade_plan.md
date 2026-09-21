# 变道降级与感知健康（方案）

> 配套 [multi_cam_contract.md](./multi_cam_contract.md)、[backlog.md](./backlog.md)。**禁止半套变道**。

## 原则

```text
变道允许 = Ego ∧ Near(surround) ∧ RCM ∧ 走廊就绪 ∧ …
任一故障 → lc_inhibit（禁止变道）；跟车可保留（FCM 可用时）
```

## 健康判据

| 源 | 健康 | 不健康 |
|----|------|--------|
| EgoMotion | ≤100–200 ms 新鲜 | 超时 |
| FreespaceNear | 新鲜 + valid | 沉默/挂 |
| Perception_Rear_Out_St | 新鲜 + valid=1 | 沉默 / valid=0 |
| 走廊 | 几何就绪 | 未实现 → 不许变道 |

`FuseDrivingFs`：缺 Near 时 `rear_*_free` **必须 false**（**已修**默认值）。

P1 已落：`MakeLcGate` / `ApplyLcInhibit`；无走廊恒 `inhibit`；`gear_shift_second=0`；reason 变化打 `[lc]`。

P2 已落：健康故障 **上升沿** `ReportEvent(process, LcInhibit*)` → Collector → PER。走廊-only 不报 DTC。

## Collector DTC（ADC `collector.yaml`）

| event_id | DTC | 上报 |
|----------|-----|------|
| `LcInhibitEgo` | `0xC01C01` | 上升沿 |
| `LcInhibitSurround` | `0xC01C02` | 上升沿 |
| `LcInhibitRcm` | `0xC01C03` | 上升沿 |
| `LcInhibitCorridor` | `0xC01C04` | 表已备；P3 前走廊-only **不** ReportEvent |

需 **compose** 刷新 `collector_config.hpp` 后板端/SIL 才吃到新 map。

## 阶段

| | 内容 | 状态 |
|--|------|------|
| P0 | Ego 三感知；stale 沉默 | 已落 |
| P1 | `lc_inhibit` 压旗；无走廊恒 inhibit；`[lc]` | 已落 |
| P2 | ego/near/rcm → Collector DTC | 已落 |
| P3 | 走廊 + 真变道（仍受健康门） | BL-LC-P3 |

## 验收口诀

Ego 断 → surround/RCM 不发。surround/RCM 挂 → 不能变道且有 error/PER。无走廊 → 不能变道。Near 坏 → `rear_*_free=false`。
