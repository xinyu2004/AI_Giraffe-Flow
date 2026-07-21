# OTA Spike（P2-U · 选型一页）

> 状态：P2 **可选**收口文档；**不做**真台架升级。  
> 相关：[PHM_OTA_PAUSE.md](PHM_OTA_PAUSE.md) · `platform/ucm.yaml` · `middleware/ucm`

## 结论（先读）

| 项 | P2 选型 |
|----|---------|
| 更新编排入口 | **UCM**（`ara::ucm` 语义状态机；配置空壳 `platform/ucm.yaml`） |
| 后端候选 | **RAUC**（优先写入 `deps/versions.lock.md`）；SWUpdate 不作为主路径 |
| PHM 配合 | 更新窗 **`SetPaused(true)`**；结束 Unpause + 立刻 Alive |
| 真包 / A/B 分区 | **→ P3** 台架演练 |

## 为什么是 RAUC

- 车载 Linux 常见 A/B；与「源码构建、可钉扎」策略一致
- UCM 只负责状态机与进度；具体刷写委托后端
- P1 stub 已覆盖 Idle→Transfer→Process→Activate→Rollback；P2 不换 API

## 与主链 SIL 的边界

```text
正常 SIL：exec Offer→Running + phm Alive（可读 platform）
故障注入：GF_PHM_FAULT_MS（缺狗）—— 不是 OTA
OTA Pause：策略豁免 Evaluate —— P2 只文档 + API；无 UCM→Pause 全自动编排
```

## P3 最小演练（预告）

1. 选一块 ARM 板 + A/B slot  
2. UCM Activate 前 SM 通知各 supervised entity Pause  
3. RAUC 刷写 → 成功 Unpause / 失败 Rollback  
4. 证据进发版 `evidence_pack`（P3-5）

## 验收（本 Spike）

- [x] 选型写明（RAUC + UCM 状态机）
- [x] 与 PHM Pause 关系有文档
- [ ] 真包升级（明确 **不在 P2**）
