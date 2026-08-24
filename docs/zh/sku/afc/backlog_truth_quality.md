# Backlog: Truth → FCM 质量字段（全 scenario）

状态：**open**（修「一坨」几何门控已落地；本项是**非几何**质量语义，等改 `carla_scenarios` 时一并做）

## 范围

对 **全部** `carla_scenarios` case（纵向 / 横向 / weather / ISP / lighting / roadway / perception…）检查并补齐假感知质量链路，**不限于 ISP**。

## 目标

`carla_truth` → FCM Out 中与「场景条件」相关的质量要可区分，而不只是车道几何门控：

| 通道 | 用途 | 场景例 |
|------|------|--------|
| LH/LA `Confidence` / `Availability` / `VR_*` | 线模型可信度（几何门控已覆盖病态 poly） | 全部；雨雾/夜间可再下调 |
| `Perception_FS_Out`（若 SIL 已透出） | 成像/失效：雨雾遮挡逆光等 | ISP 隧道、weather、lighting |
| DYN `Existence` / `Class` 概率 | 目标可见性 | 遮挡 AEB、夜间前车 |

## 验收

- [ ] 每个域至少 1 个 case：truth 带质量字段，FCM 赋值与 case 条件一致（clear 高 / 恶劣低）
- [ ] BEV / planning 已守 Out 门控（几何部分已做）；恶劣天气下线/目标置信可见下降
- [ ] 文档：`frame_ingest_roles.md` 或本文更新「质量契约」一句

## 不做（本 backlog）

- 弯道 C2 观感优化（另项）
- 金样折线扩展

## 关联

- 已做：几何失效 → `lane_avail` / `lane_conf` / `lane_vr_end_m` → FCM → BEV 守 VR（消「一坨」）
- 触发时机：下次系统改 `carla_scenarios` 假感知/布景时一起做，勿单独散改
