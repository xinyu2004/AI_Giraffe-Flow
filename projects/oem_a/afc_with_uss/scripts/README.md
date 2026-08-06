# Project scripts — oem_a / afc_with_uss

SIL ≈ HIL（仅工具链不同）。配置真相 = gf-config → compose 生成物。

**产品主路径（四入口）**

| Script | Purpose |
|--------|---------|
| [compile_sil.sh](compile_sil.sh) | host：compose → generate → cmake → ctest |
| [compile_hil.sh](compile_hil.sh) | 交叉编译 → `build-hil/` |
| [run_sil.sh](run_sil.sh) | 主链 bring-up；`live_tap` 有效时自动 Foxglove WS |
| [run_hil.sh](run_hil.sh) | 板端对等（部署后续） |
| [_common.sh](_common.sh) | 共享路径 / compose |

**FuSa 产物（非主路径，与 `fusa/scripts/run_cases.sh` 独立）**

| Script | Purpose |
|--------|---------|
| [generate_fusa_artifacts.sh](generate_fusa_artifacts.sh) | compose/SOR/lineage（+可选 smoke）→ `fusa/packs/oem_a_afc_with_uss/` |

```bash
# 主路径（默认主机 GCC）
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# Studio → ws://127.0.0.1:8765（需 A 页 live_tap 开 + vehicle-debug）

# 已编过
GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# P2.5：换主机编译器（建议独立 build 目录；换编译器时依赖也隔离）
GF_CC=clang GF_CXX=clang++ GF_BUILD_DIR=$PWD/build-clang \
  bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
# 或 toolchain 文件：
# GF_SIL_TOOLCHAIN_FILE=cmake/toolchains/host-clang.cmake GF_BUILD_DIR=$PWD/build-clang \
#   bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
```

| Env | 含义 |
|-----|------|
| `GF_CC` / `GF_CXX` | 主机编译器 |
| `GF_SIL_TOOLCHAIN_FILE` | 可选 CMake toolchain（覆盖 CC/CXX） |
| `GF_BUILD_DIR` | SIL 输出（默认 `projects/.../build-sil`） |
| `GF_OBS_OUT` | session/MCAP 根（默认 `${BUILD}/observability`） |
| `GF_DEPS_PREFIX` | 依赖前缀；换编译器时避免与 GCC deps 混链 |
| `GF_INJECT_SESSION` | 若设置：回灌（**不起 gateway**；跑 `gf_iox_obs_inject`） |
| `GF_INJECT_SERVICES` | 回灌服务短名（默认 `EgoMotion`；B2 可从 DUT requires 自动推导） |
| `GF_INJECT_DUT` | **B2**：SOR process（如 `sensing.uss`）→ 只起该 DUT + inject |
| `GF_INJECT_APPS` | **B2** 覆盖：逗号列表 `uss,fcm,planning`（不查 SOR） |
| `GF_LIVE_TEE` | live_tap 时 tee NDJSON→session（默认 `1`；`0` 关闭） |
| `GF_LIVE_SESSION` | tee 目标（默认 `${BUILD}/observability/session_live.jsonl`） |

**验证 / smoke**（非产品路径）→ [`verify/`](verify/)（与工程同树；仓根 `scripts/verify/oem_a_*` 仅为 deprecated shim）

| gf-config | compile_sil | run_sil |
|-----------|-------------|---------|
| bindings iceoryx/dds | `GF_WITH_*` | 有 iceoryx → RouDi |
| live_tap（debug+开+白名单） | 编 `iox_obs_tap` | `tap \| GMT --ws` |
| vehicle-debug | 另编 `iox_obs_inject` | `GF_INJECT_SESSION=…` → 无 gateway |
| apps | 业务 app（勿手写 tap/inject） | 主链进程 |

```bash
# B1 回灌（验证）：全消费者链，无 gateway
bash projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_inject.sh

# B2 单模块（验证）：只起 sensing.uss + inject
bash projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_inject_b2.sh
# 或手工：
# GF_SKIP_COMPILE=1 GF_INJECT_SESSION=projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
#   GF_INJECT_DUT=sensing.uss bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

Generated: `../generated/`（gitignored）。
