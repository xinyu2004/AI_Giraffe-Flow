# Project scripts — oem_a / afc_with_uss

SIL ≈ HIL（仅工具链不同）。配置真相 = gf-config → compose 生成物。

**产品主路径**

| Script | Purpose |
|--------|---------|
| [compile_sil.sh](compile_sil.sh) | 增量：mtime compose / 按需 cmake configure / build；默认跳过 ctest（`GF_CTEST=1`）；stage → `runtime/` + `giraffe_launch` |
| [compile_hil.sh](compile_hil.sh) | 交叉编译 → `build-hil/`；同样按需 configure |
| [stage_sil_runtime.sh](stage_sil_runtime.sh) | 打 `runtime/` 包（默认**不**拷 `platform/`；`GF_STAGE_PLATFORM=1` 才拷） |
| [run_sil.sh](run_sil.sh) | compile → EM；默认挂 [GMT_depend_launch.sh](GMT_depend_launch.sh) |
| [GMT_depend_launch.sh](GMT_depend_launch.sh) | GMT 旁路：端口预检 + Foxglove / inject / DoIP / carla_bridge |
| [run_hil.sh](run_hil.sh) | 板端提示（日常仍用 SIL） |
| [_common.sh](_common.sh) | 共享路径 / mtime 门禁 |

**FuSa 产物（非主路径，与 `fusa/scripts/run_cases.sh` 独立）**

| Script | Purpose |
|--------|---------|
| [generate_fusa_artifacts.sh](generate_fusa_artifacts.sh) | FuSa evidence → `fusa/packs/oem_a_afc_with_uss/`；发版：`GF_FUSA_PACK_RELEASE=1`（经 `smoke_release.sh`） |

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
| `GF_FORCE_COMPILE=1` | 强制 compose + cmake configure + stage |
| `GF_CTEST=1` | 跑 ctest（默认跳过） |
| `GF_GMT_DEPEND=0` | 只 EM，不挂 GMT 旁路 |
| `GF_STAGE_PLATFORM=1` | stage 时拷贝 `platform/*.yaml`（默认不拷；板端零行为 yaml） |
| `GF_OBS_OUT` | session/MCAP 根（默认 `${BUILD}/observability`） |
| `GF_DEPS_PREFIX` | 依赖前缀；换编译器时避免与 GCC deps 混链 |
| `GF_INJECT_SESSION` | 若设置：回灌（**不起 gateway**；跑 `gf_iox_obs_inject`） |
| `GF_INJECT_SERVICES` | 回灌服务短名（默认 `EgoMotion`；B2 可从 DUT requires 自动推导） |
| `GF_INJECT_DUT` | **B2**：SOR process（如 `sensing.uss`）→ 只起该 DUT + inject |
| `GF_INJECT_APPS` | **B2** 覆盖：逗号列表 `uss,fcm,planning`（不查 SOR） |
| `GF_LIVE_TEE` | live_tap 时 tee NDJSON→session（默认 `1`；`0` 关闭） |
| `GF_LIVE_SESSION` | tee 目标（默认 `${BUILD}/observability/session_live.jsonl`） |

**验证 / smoke**（非产品路径）→ [`verify/`](verify/)

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
