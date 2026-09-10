# Giraffe Modules 根基（阶段 M）合同

> 与 [gallery/Giraffe_Modules](../../../gallery/Giraffe_Modules/README.md) 动图一致。全项目计划：先 M → 再 ADC 骨架 → 再算法/场景。

## 启动顺序（唯一正确）

```text
systemd/init → EM (gf_em_daemon) → daemons + SOA apps
                 ↓
            各 App runtime：EnsureGroup(sm) → Exec Offer → PHM Alive
```

- **EM 最先**；**sm 不是开机进程**，是进程内 `StateClient`。
- FG 态仅 **Off / Running / Updating**（无 Pending / Active）。
- 行泊产品模式（VehicleMode）属后续 **Mode Manager App**（由 EM 拉起），不画进 Modules 芯片图。

## 验收钩子

| 项 | 命令 |
|----|------|
| sm 库态机 | `ctest -R gf_sm_fg_smoke` |
| SIL-SM-01 notify_sm | `bash projects/afc/scripts/verify/smoke_sil_sm_fg.sh` |
| EM daemon | `bash projects/afc/scripts/verify/smoke_sil_em_daemon.sh` |
| PHM miss→recover | `bash projects/afc/scripts/verify/smoke_sil_phm_fault.sh` |

## 本阶段不做

ADC 业务、环视/泊车算法、VehicleMode 实现、扩展 FG Passive。
