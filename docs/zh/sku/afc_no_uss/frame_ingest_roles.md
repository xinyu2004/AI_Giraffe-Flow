# frame_ingest / camera_slot / carla_scenarios 职责

## 主路径

```text
gf-config（Save → Verify → 可选 Generate）→ compile_sil → runtime/{bin,lib} → run_sil → GMT
```

- **帧源**：freeze SOP 默认 `isp`（进 `frame_ingest_config.hpp`）；SIL 用 **`GF_FRAME_SOURCE`** 覆盖：`isp` / `carla` / `replay` / `colorbar`（旧名 `synth`）/ `none`。与 `GF_INJECT_MODE`（ego/SOA 注入）正交。次要覆盖：`GF_ACTIVE_SOURCE`。
- **ego_source**：`gateway` / `carla` / `inject` — 同样冻结；gateway/FCM/ingest 读 constexpr，**不要**靠 `run_sil` grep hpp。
- **`carla_scenarios/`**：独立 Client A 场景机；**零** compose / stamp / runtime 合同；勿与帧源混称「场景」。
- **compile / run 不 compose**：改 camera_slots 后须在 gf-config **Verify**；`compile_sil` / `run_sil` 只编/跑已有 `generated/`。

## 与 carla_scenarios 同步（相机契约）

gf-config **不**把配置「推」进场景机。compose 写出只读契约，场景机按路径读：

```text
gf-config Save/Verify
  → compose
  → projects/<sku>/generated/camera_contract.json   ← 槽位 / WxH / pixel / mount
  → projects/<sku>/generated/include/gf_gen/frame_ingest_config.hpp  ← 板端/SIL 行为
```

场景机侧（`carla_scenarios/src/lib/_camera_mount.py`）**只读契约**，无本地 preset、无 `GF_CAMERA_MOUNT_*` 手写几何：

1. **`GF_CAMERA_CONTRACT=/绝对路径/camera_contract.json`**  
2. 否则 **`$GF_PROJECT_DIR/generated/camera_contract.json`**  
3. 否则仓库相对路径 `projects/oem_a/afc_no_uss/generated/camera_contract.json`（若存在）  
4. 都没有 / 字段不全 → **硬退出**（不发明数字）

```bash
# 例：Windows/另一台机跑场景时显式对齐
export GF_CAMERA_CONTRACT=/path/to/afc_no_uss/generated/camera_contract.json
# 或
export GF_PROJECT_DIR=/path/to/afc_no_uss
cd carla_scenarios && python3 cases/longitudinal/acc.py
```

不需要拷贝进 `carla_scenarios/`；改 camera_slots 后 **重新 compose**，场景机下次启动即读到新契约。SIL camera 写端（`carla_bridge`）优先用 ingest 从 hpp `SetEnv` 的 `GF_CAMERA_MOUNT_*`，缺省时同样读 `camera_contract.json`。

## 常驻 `gf_frame_ingest`（C++）

帧源非 `none` 时，compose 把 `host.frame_ingest`（`bin/gf_frame_ingest`）冻进 `deploy_config.hpp`，由 **EM** 启动。`run_sil` 产品路径不再 shell 起一份；GMT inject 停 EM 后由 `GMT_depend_launch.sh` 可选再启。

### 板端 vs 宿主机 SIL（零 Python 政策）

| 环境 | `gf_frame_ingest` 行为 | Python |
|------|------------------------|--------|
| **板端 / 上板 runtime** | C++ only：Create GfChannel + ISP/V4L 等适配 | **禁止**（解释器与 `share/**/*.py` 一律不上板） |
| **宿主机 SIL** | Create 槽后可 spawn 模块（`--module-only`） | 允许：`carla` / `colorbar` / `replay` |

政策见 [CONFIG_RUNTIME_POLICY.md](../../operations/CONFIG_RUNTIME_POLICY.md) 与 backlog `BL-BOARD-NO-PY`：**凡 GMT/EM 会拉上板的依赖都按板端口径收口**，不只是 ISP 源本身。

SIL 路径细节：

- 冻结 `kBridgeEnabled=false` 或 `kActiveSource=none` → **立即 exit 0**
- 否则 Create GfChannel，再 spawn Python 模块（`--module-only`）— **仅 SIL**
- so 在 `runtime/lib/libgf_gf_channel.so`（RPATH / `LD_LIBRARY_PATH`）
- `modules/carla_bridge` 由 stage **实体拷贝**进 `share/frame_ingest/`（非绝对 symlink；改 py 后注意 `BL-STAGE-PY-MTIME`）

| 角色 | 负责 | 不负责 |
|------|------|--------|
| **gf_frame_ingest (C++)** | 读 hpp；Create 槽；板端跑适配 / SIL 可 spawn 模块 | 布景、ACC 剧情 |
| **模块 carla（仅 SIL）** | 相机→YUV、ego、执行 cmd | spawn hero |
| **GfChannel** | shm 图像槽 | ARA 事件 |
| **FCM** | Open+Latest | Create |
| **carla_scenarios（仅主机）** | Client A 布景+IC | 写 camera / 进 compose |

## runtime = SIL 运行根 = HIL 板端载荷

完整树见 [runtime_package.md](./runtime_package.md)。摘要：

```text
runtime/{bin,lib,etc,platform,share}
```

- `bin/`：`gf_em_daemon`、`iox-roudi`、`dlt-daemon`、SOA apps、`gf_frame_ingest`（及 debug 用 `giraffe_launch`）
- `lib/`：`libgf_ara_*.so`、`libgf_osal.so`、`libgf_gf_channel.so`、`libdlt.so*`（无 `*_sil_stub`）
- 入口：`./bin/gf_em_daemon`（或设 `GF_BUILD_DIR=runtime` 后起 EM）；板端 stage **不得**打进 Python 模块

本机粗评（SHARED + strip 后约 **4.3 MiB**，相对原先静态 app stage ~69 MiB）。

```bash
du -sh projects/oem_a/afc_no_uss/build-sil/runtime
```

## compile（不 compose）

`run_sil` 仍可调 `compile_sil`。增量分工：

- **作者态**：gf-config Verify（+ Generate）写出 `generated/`；**compile 不再 compose**
- **C/C++**：`cmake --build` → Ninja/Make（文件 mtime + gcc `-MD` depfile）
- **stage**：runtime 缺件或 build 产物更新才拷
- **ctest**：默认跳过；`GF_CTEST=1` 才跑
- 强制：`GF_FORCE_COMPILE=1`（强制 cmake configure + stage）

## GfChannel vs iceoryx

| | iceoryx | gf_channel |
|--|---------|-------------|
| 负载 | 结构化事件 | 大块图像 |
| RouDi | 需要 | 不需要 |

## 录 25fps 回灌

```bash
GF_CARLA_SYNC=1 GF_CAMERA_RECORD_FPS=25 GF_RECORD_FRAMES_DIR=/tmp/camera_vol \
  bash projects/oem_a/afc_no_uss/scripts/run_sil.sh
# 帧源改成 replay 后：gf-config Verify → compile_sil，或调试：
GF_INJECT_FRAMES_DIR=/tmp/camera_vol …
```

## client / server（HIL）

| 角色 | 是什么 |
|------|--------|
| Server | CARLA UE |
| Client A | `carla_scenarios`（独立机/进程） |
| Client B | SIL `gf_frame_ingest` |

```text
Windows:  carla_scenarios → cases ──RPC──┐
                                         ├→ UE
Linux:    EM → runtime/bin/gf_frame_ingest ─┘
          GfChannel(shm) → FCM
```

## carla.env

| 文件 | 谁读 |
|------|------|
| `projects/.../carla.env` | `run_sil`（仅 SKU；UE IP / Python） |
| `carla_scenarios/carla.env` | **仅**场景机；SIL **不加载** |

## 验收

- 无脚本 grep `frame_ingest_config.hpp`
- 二次 `compile_sil`：compose/stage 可 mtime-skip；`cmake --build` 由 Ninja 增量
- **注意：** `tools/carla_bridge/*.py` 不经编译；若 stage 被 skip，runtime 里可能仍是**旧拷贝**（ingest 优先 `share/frame_ingest/modules/`）。改 bridge 后需 `stage_sil_runtime` / `GF_FORCE_COMPILE=1`，或修 `BL-STAGE-PY-MTIME`
- `runtime/` 可 `du`；含 `bin/gf_frame_ingest` + `lib/libgf_gf_channel.so`
- **假感知：`carla_scenarios` 写 `runtime_ipc/carla_truth.json` → **仅 FCM** 读入并填金样 `Perception_MESSAGE_Out_St`（DYN 多目标/行人 + LH/LA 含 C2）→ iceoryx → planning / Foxglove BEV。planning **不再**读 truth 文件。
- **金样字段 / planning lite 归档：** [../../driving/fcm_gold_and_planning_lite.md](../../driving/fcm_gold_and_planning_lite.md)（用了哪些 Out 变量、干什么、lite 控车做了什么）。

## Demo 量程与颜色（afc_no_uss）

| 量 | 值 | 说明 |
|----|----|------|
| `D_work` | **≈120 m** | 软工作带（跟车/有效检测参考）；**不是** BEV 硬裁边界 |
| `D_bev` | **130 m** | 画布 ≈ `D_work×1.1`；车道线/刻度/目标按此绘制，避免余量漏画 |
| 颜色 | **按 `m_OBJ_ID` 调色板** | 相邻可辨；CIPV 加浅描边；以后视频叠框共用 ID→色 |
| UE↔BEV | **车道锚** | BEV 以本车道航向为 +x；车身/目标按相对航向旋转，避免横车挤扁 |
| 多目标 | truth→FCM | 周围车辆+行人进 `m_Obj_item`；类别映射 CARLA→金样 enum |
| 车道拓扑 | **truth→FCM→LH+LA** | BEV **只画 Out**；禁止示意臆造车道数/本车道索引 |
| `ego_lane_index_from_left` | 从左数 0… | 真值字段；本车道由 LH 体现 |

多车道 / 视频叠框后置；本阶段 LH 仍为本车道示意。

## Backlog

- 全 scenario 质量字段（Confidence / FS / 非仅 ISP）：见 [backlog_truth_quality.md](./backlog_truth_quality.md)（改 carla_scenarios 时一并做）。
