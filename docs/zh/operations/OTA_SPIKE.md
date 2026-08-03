# OTA Spike（P2-U · 选型史）

> **P3-4 操作面与字段说明请读：[DOIP_OTA.md](DOIP_OTA.md)**（权威）。  
> 本文保留 P2 选型结论；真台架升级仍不在桌面主航道（→ P3z）。

## 结论（先读）

| 项 | 选型（仍有效） |
|----|----------------|
| 更新编排入口 | **UCM**（`ara::ucm` 语义状态机；`platform/ucm.yaml`） |
| 后端候选 | **RAUC**（优先写入 `dep-manifest/versions.lock.md`）；SWUpdate 不作为主路径 |
| PHM 配合 | 更新窗 **`SetPaused(true)`**；结束 Unpause + 立刻 Alive → [PHM_OTA_PAUSE.md](PHM_OTA_PAUSE.md) |
| 桌面路径（P3-4） | DoIP + UDS（默认 **0x38**）→ UCM stub Activate；见 [DOIP_OTA.md](DOIP_OTA.md) |
| 真包 / A/B 分区 | **→ P3z** |

## 为什么是 RAUC

- 车载 Linux 常见 A/B；与「源码构建、可钉扎」策略一致
- UCM 只负责状态机与进度；具体刷写委托后端
- P1 stub 已覆盖 Idle→Transfer→Process→Activate→Rollback；API 未换

## 与主链 SIL 的边界

```text
正常 SIL：exec Offer→Running + phm Alive（可读 platform）
故障注入：GF_PHM_FAULT_MS（缺狗）—— 不是 OTA
OTA Pause：策略豁免 Evaluate —— 编排 hook / Updating FG
DoIP OTA：GMT → gf_doip_ota_server → UCM（非真刷写）
```

## 验收

- [x] 选型写明（RAUC + UCM 状态机）
- [x] 与 PHM Pause 关系有文档
- [x] P3-4 桌面 DoIP/GMT 路径（见 DOIP_OTA）
- [ ] 真包升级（明确 **P3z**）
