# inject 三种模式（本 SKU）

目录与模式一一对应（均在 `samples/inject/`）：

| 目录 | 模式 | 典型环境变量 |
|------|------|----------------|
| `continuous/` | 文件连续回放 | `GF_INJECT_SESSION=…` `GF_INJECT_MODE=continuous` |
| `playhead/` | GMT 时间轴驱动 | `GF_INJECT_MODE=playhead`（session 可选） |
| `dut/` | B2 单模块 | `GF_INJECT_DUT=…` + session |

互斥：`ego_source=inject` 时 gateway **不**发 EgoMotion。

```bash
./samples/stage.sh --inject playhead
export GF_EGO_SOURCE=inject
# 按 stage 输出 export 后：
bash projects/oem_a/afc_no_uss/scripts/run_sil.sh
```

带帧回灌：目录下提供 `frames/`（`stream.json` + 平面），并 `export GF_INJECT_FRAMES_DIR=…`。
