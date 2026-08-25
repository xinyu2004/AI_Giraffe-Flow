# Backlog: Truth → FCM 质量字段（全 scenario）

状态：**open**（几何门控已落地；本项是**非几何**质量语义）

## 范围

对 **全部** `carla_scenarios` case 检查并补齐假感知质量链路。  
生产者现为 `giraffe_client` → `_lane_truth` / `_objects_truth` → `GfFakePercPod`（不再写 `carla_truth.json`）。

## 目标

`fake_perc` → FCM Out 中与「场景条件」相关的质量要可区分，而不只是车道几何门控：

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

- 已做：几何失效 → `lane_avail` / `lane_conf` / `lane_vr_end_m` → FCM → BEV 守 VR
- 已做：假感知生产者迁到 cosim POD（对齐旧 JSON 字段）
- 触发时机：下次加深天气/ISP 质量映射时一起做
