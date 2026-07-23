# Project scripts — oem_a / afc_with_uss（产品主路径，仅四入口）

SIL ≈ HIL（仅工具链不同）。配置真相 = gf-config → compose 生成物。

| Script | Purpose |
|--------|---------|
| [compile_sil.sh](compile_sil.sh) | host：compose → generate → cmake → ctest |
| [compile_hil.sh](compile_hil.sh) | 交叉编译 → `build-hil/` |
| [run_sil.sh](run_sil.sh) | 主链 bring-up；`live_tap` 有效时自动 Foxglove WS |
| [run_hil.sh](run_hil.sh) | 板端对等（部署后续） |
| [_common.sh](_common.sh) | 共享路径 / compose |

```bash
# 主路径
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# Studio → ws://127.0.0.1:8765（需 A 页 live_tap 开 + vehicle-debug）

# 已编过
GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

**验证 / smoke**（非产品路径）→ [`scripts/verify/oem_a_afc_with_uss/`](../../../../scripts/verify/oem_a_afc_with_uss/)

| gf-config | compile_sil | run_sil |
|-----------|-------------|---------|
| bindings iceoryx/dds | `GF_WITH_*` | 有 iceoryx → RouDi |
| live_tap（debug+开+白名单） | 编 `iox_obs_tap` | `tap \| GMT --ws` |
| apps | 业务 app（勿手写 tap） | 主链进程 |

Generated: `../generated/`（gitignored）。
