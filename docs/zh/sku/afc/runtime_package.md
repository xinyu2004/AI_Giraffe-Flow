# Runtime package (board-complete) + footprint

## 入口对照

板端与主机调试差很小（编译器 / 依赖 / 少量地址配置）；**不是两套产品**。

| 场景 | 入口 | 做什么 |
|------|------|--------|
| 产品 EM（主机或板端） | `runtime/bin/gf_em_daemon / gf_em_daemon / giraffe_launch(debug)(debug)` | 起 EM（dlt?/RouDi?/frame_ingest?/SOA）；名字可改 |
| 调试联调（主机 SIL 或板端前期） | `scripts/run_sil.sh` | compile → EM → 默认挂 `GMT_depend_launch.sh` |
| 只要 EM、不要 GMT 旁路 | `GF_GMT_DEPEND=0` + `run_sil.sh`，或直接 `gf_em_daemon / gf_em_daemon / giraffe_launch(debug)(debug)` | 无 Foxglove / inject / DoIP |
| GMT inject | `GF_INJECT_MODE=playhead` 等 | `GMT_depend_launch` 停 EM，再起 RouDi+consumers+inject |

配置真源：`gf-config → compose → deploy_config.hpp`。`GF_CARLA_*` 仅调试覆盖；相机路径默认在 ingest/gateway 二进制内。`carla_bridge` 以实体拷贝进 `share/frame_ingest/modules/`（非绝对 symlink）。

## Layout

```text
build-sil/runtime/
  bin/     gf_em_daemon / gf_em_daemon / giraffe_launch(debug)(debug), gf_em_daemon, iox-roudi, dlt-daemon, gf_frame_ingest, apps
  lib/     libgf_ara_*.so, libgf_osal.so, libgf_channel.so, libdlt.so*
  etc/     iox_roudi.toml
  platform/  SKU yaml（作者态/兼容；行为真源在 hpp）
  share/frame_ingest/
    gf_frame_ingest.py, gf_channel_py.py
    modules/carla_bridge/   # staged copy
```

## 运行

```bash
# 拷 runtime/ 到目标机后（主机或板端同一入口）:
./bin/gf_em_daemon / gf_em_daemon / giraffe_launch(debug)(debug)
# 或:
export GF_BUILD_DIR=$PWD GF_PLATFORM_DIR=$PWD/platform \
  GF_IOX_TOML=$PWD/etc/iox_roudi.toml LD_LIBRARY_PATH=$PWD/lib
./bin/gf_em_daemon
```

主机日常调试仍可用 `bash …/scripts/run_sil.sh`（含 compile + GMT depend）。

## Size (afc host SIL, stripped)

| | Before (static apps only stage) | After (SHARED + full stage) |
|--|--------------------------------|-----------------------------|
| total | ~69 MiB | ~4.3 MiB |
| FCM | ~18 MiB | ~132 KiB |
| gateway | ~17 MiB | ~108 KiB |

Giraffe is now shared under `lib/`; apps no longer each embed a full copy.

## Notes

- `libgf_diag_sec*.so` is **not** staged by default (optional 0x27 plugin; formal name `libgf_diag_sec.so` if needed via `GF_STAGE_DIAG_SEC=1`).
- `GF_STAGE_NO_STRIP=1` keeps symbols for debug.
- iceoryx is largely inside `libgf_ara_com_iceoryx.so` + `iox-roudi`; further third-party dynamicization is optional.
- Compat: `bin/run_on_target.sh` → symlink to `gf_em_daemon / gf_em_daemon / giraffe_launch(debug)(debug)`（旧名）。
