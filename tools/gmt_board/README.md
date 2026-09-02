# tools/gmt_board

GMT 的板端 / SIL 旁路（非量产路径）：tap、inject、Foxglove WS。不在控车主链上。

| App id（`GF_APPS`） | Binary | 作用 |
|--------------------|--------|------|
| `gmt_board/iox_obs_tap` | `gf_iox_obs_tap` | 白名单服务 → NDJSON（GMT 录制） |
| `gmt_board/iox_obs_foxglove` | `gf_foxglove_ws` | iceoryx → Foxglove Studio（`:8765`，含 BEV） |
| `gmt_board/iox_obs_inject` | `gf_iox_obs_inject` | EgoMotion 等回灌（playhead / continuous） |

compose 按 profile 自动加入；勿手写进 `req.apps`。`production-release` 不编这三项。

| | 路径 |
|--|------|
| **源码** | `tools/gmt_board/`（本目录） |
| **产物** | `$GF_BUILD_DIR/apps/gmt_board/...` |

没有物理目录 `apps/gmt_board/`；compose id 与 CMake 产物目录对齐。
