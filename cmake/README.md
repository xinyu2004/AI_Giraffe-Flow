# cmake/

Shared build modules for Giraffe Flow.

| File | Role |
|------|------|
| [Dependencies.cmake](Dependencies.cmake) | iceoryx / ACL from `middleware/third_party` + `.deps-prefix` |
| [GfModules.cmake](GfModules.cmake) | **SKU 裁剪**：按 `GF_RUNTIME_MODULES` / `GF_APPS` / `GF_WITH_*` 加目录 |
| [profiles/](profiles/) | `desktop_*` / `mcu_desktop` / `eu_stub` / `bd_stub` |
| [toolchains/](toolchains/) | aarch64 / armhf 交叉 |

## req.yaml → CMake（F 轨）

```text
req.yaml  ──compose──►  projects/<sku>/generated/gf_build.cmake
                              │
                              ▼
              cmake -DGF_SKU_CMAKE=.../gf_build.cmake
                              │
              Dependencies  →  GfModules  →  targets
```

| req 字段 | CMake | 行为 |
|----------|-------|------|
| `bindings: [iceoryx]` | `GF_WITH_ICEORYX=ON` | `middleware/bindings/iceoryx` |
| `bindings: [cross_domain_ipc]` | `GF_WITH_CROSS_DOMAIN_IPC` | `middleware/bindings/cross_domain_ipc` |
| `bindings: [someip]` | `GF_WITH_SOMEIP` | 有 CMakeLists 才加；否则 STATUS 跳过 |
| `bindings: [dds]` | `GF_WITH_DDS` | 同上 |
| `runtime_modules` | `GF_RUNTIME_MODULES` | 除 always-on 外按名 `add_subdirectory`；无 CMakeLists 则跳过 |
| `apps` | `GF_APPS` | `apps/<path>`；iceoryx demo 需 iceoryx；MCU apps 需 cross_domain_ipc |

**Always-on（不论 req）：** `core` · `com` · `osal`

**无 `-DGF_SKU_CMAKE` 时：** 用 [profiles/desktop_default.cmake](profiles/desktop_default.cmake)。

**MCU 桌面联调（无 iceoryx）：** [profiles/mcu_desktop.cmake](profiles/mcu_desktop.cmake) + `projects/oem_b/adc_full/scripts/smoke_mcu_desktop.sh`。

**E/U stub（exec/phm/ucm/diag）：** [profiles/eu_stub.cmake](profiles/eu_stub.cmake) + `scripts/smoke_eu_stub.sh`。

**B/D stub（DDS + SOME/IP）：** [profiles/bd_stub.cmake](profiles/bd_stub.cmake) + `scripts/smoke_bd_stub.sh`；IDL：`gf-codegen emit-idl` + `scripts/run_idlc.sh`。

**低配示例（afc_no_uss）：** compose 后仅 iceoryx + `demo_pipeline`；`log`/`exec`/… 无实现则 STATUS 跳过，不失败。

SIL：`compile_sil.sh` 已传 `-DGF_SKU_CMAKE=<proj>/generated/gf_build.cmake`。
