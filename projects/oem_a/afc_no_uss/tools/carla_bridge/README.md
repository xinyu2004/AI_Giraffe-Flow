# carla_bridge (Client B tip module)

Camera → GfChannel / ego / cmd. World / ACC stories: repo `carla_scenarios/` (Client A) — **no import**.

Camera mount / extrinsics (one truth): compose → hpp. At runtime `gf_frame_ingest`
`SetEnv` `GF_CAMERA_MOUNT_*` (legacy `GF_CARLA_TIP_*` still set); `camera_mount.py`
reads those, or falls back to `generated/camera_contract.json`
(`GF_CAMERA_CONTRACT` / `GF_PROJECT_DIR`). No local preset table. Scenarios read
the same `camera_contract.json` only via `_camera_mount.py`.
