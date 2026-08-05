# tools/debug_bridge

SIL 观测旁路工具（非量产路径）：

| App id（`GF_APPS`） | Binary | 作用 |
|--------------------|--------|------|
| `debug_bridge/iox_obs_tap` | `gf_iox_obs_tap` | 白名单服务 → NDJSON / Foxglove / GMT live |
| `debug_bridge/iox_obs_inject` | `gf_iox_obs_inject` | EgoMotion 等回灌（playhead / continuous） |

compose 按 profile 自动加入；勿手写进 `req.apps`。

| | 路径 |
|--|------|
| **源码** | `tools/debug_bridge/`（本目录） |
| **产物** | `$GF_BUILD_DIR/apps/debug_bridge/...`（默认 `projects/.../build-sil/apps/debug_bridge/`） |

没有物理目录 `apps/debug_bridge/`；compose id 与 CMake 产物目录对齐。
