# tools/gmt_board

GMT 的板端 / SIL 旁路（非量产路径）：tap、inject、Foxglove WS。不在控车主链上。

| App id（`GF_APPS`） | Binary | 作用 |
|--------------------|--------|------|
| `gmt_board/iox_obs_tap` | `gf_iox_obs_tap` | 白名单服务 → NDJSON（GMT 录制） |
| `gmt_board/iox_obs_foxglove` | `gf_foxglove_ws` | iceoryx → Foxglove Studio（`:8765`，含 BEV） |
| `gmt_board/iox_obs_foxglove` | `gf_host_bev_ws` | Host octave 单机：stdin NDJSON → **同一** `bev_compose` paint → Foxglove（无 iceoryx） |
| `gmt_board/iox_obs_inject` | `gf_iox_obs_inject` | EgoMotion 等回灌（playhead / continuous） |

**BEV 金源：** `iox_obs_foxglove/src/bev_compose.cpp`（`gf_foxglove_paint`）。SIL 走 `gf_foxglove_ws`；Host 走 `gf_host_bev_ws`（`GF_HOST_BEV_BIN`）。已删除 Python `gf_gmt.bev_compose`。

compose 按 profile 自动加入；勿手写进 `req.apps`。`production-release` 不编 tap/inject/`gf_foxglove_ws`（Host paint 目标仍可单独编）。

| | 路径 |
|--|------|
| **源码** | `tools/gmt_board/`（本目录） |
| **产物** | `$GF_BUILD_DIR/apps/gmt_board/...` |

没有物理目录 `apps/gmt_board/`；compose id 与 CMake 产物目录对齐。
