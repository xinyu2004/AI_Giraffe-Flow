# frame_ingest

- **Binary**: `gf_frame_ingest` — Create camera GfChannel from `frame_ingest_config.hpp`, then **exec** an independent C++ module
- **Modules** (separate apps):
  - `gf_frame_colorbar`
  - `gf_frame_replay`
  - `gf_carla_io`
- **No Python** on the boundary path

Board: `isp` holds slots (C++ only). SIL: set `GF_FRAME_SOURCE=colorbar|replay|carla`.
