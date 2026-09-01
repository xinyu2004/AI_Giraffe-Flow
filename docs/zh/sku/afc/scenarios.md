# 产品场景（carla_scenarios）

CARLA **Client A**：布景 + IC；连续控车仅 Giraffe→bridge。实现代码在 `carla_scenarios/src/`。

```text
carla_scenarios/
  README.md          # 指向本文档（中英入口）
  run_cases.py       # ★ 批跑入口 → results/runs/<时间戳>/
  carla.env          # 默认旋钮（duration 等；CLI 可覆盖）
  manifest.yaml
  cases/             # 产品 case
  results/           # 仅批跑写出（单 case 不写）
  src/
    spawn/           # pick / place / ic / boundary / roles
    layouts/         # 按布景族组合积木（≠ cases 产品域目录）
    lib/             # AtomCase、view、verdict、carla_env…
    judges/
```

## 架构快照（Client A）

| 层 | 路径 | 一句话 |
|----|------|--------|
| 产品清单 | `cases/**/manifest.yaml` | 只列 id/script/status/keyword…，零 layout/spawn 字段 |
| 薄 case | `cases/**/*.py` | AtomCase 绑 layout + judge + on_tick |
| 布景族 | `src/layouts/*` | 显式 `pick → place → 具名 ic` |
| 积木 | `src/spawn/{pick,place,ic,boundary,roles}` | 选点 / 落位静止 / 本案初速 / 案间消毒 / 角色 |
| 批跑 | `run_cases.py` | 长驻 Client；案间 `sanitize_keep_ego`；可选写 results |
| 门禁 | `scripts/check_spawn_import_gate.sh` | 防 follow 吃 closing、place 吃 ic 等 |

scheme-1：**scenario 只布景+IC**；连续控车应是 Giraffe→bridge。无 SIL 时仍可跑通布景，判定多为 `no_giraffe_control`（只影响结案，不代替 AEB 刹车）。

## 布景分层（manifest 零代码关联）

**原则**：`manifest.yaml` 只登记产品信息（id / script / status / keyword / tags / description），**永不**写 layout / spawn / judge / import。Case → 代码唯一入口是 `script:`；脚本内部自己引用 layout。

### 三层职责

| 模块 | 允许 | 禁止 |
|------|------|------|
| `src/spawn/pick.py` | 返回 transform | 碰 actor、速度、keep_ego |
| `src/spawn/place.py` | spawn / destroy / clear_near / 重试 | 恒速、按 case 分支、settle+IC |
| `src/spawn/ic.py` | **具名** IC profile | 被 place/pick 内部悄悄调用 |
| `src/layouts/*` | 显式 `pick → place → ic_xxx` | 改 `spawn.*` 全局默认；在共享函数里加 `if case_id` |

生命周期（动态解耦）::

```text
place（落位+静止）→ 具名 case IC（只给本案初速）→ run/judge
        ↑                                         │
        └──── boundary.sanitize_keep_ego ◄─────────┘  （批跑/combo）
```

- **boundary**（`spawn/boundary.py`）：唯一拥有 keep_ego 残速；出口 `|v|≈0`；失败则 **销毁 hero**（keep_ego 降级）。
- **place**：只保证位姿与静止；不给恒速、不纠倒车。
- **case IC**：假定 boundary 已干净；禁止 flip/残速救场。

具名 IC：

- `release_only` — ACC / weather follow
- `closing_toward_lead` — 车车 AEB/FCW
- `closing_along_heading` — 贴道路朝向（VRU ego、同向自行车）
- `closing_along_pose` — 横穿车当前朝向（勿用于 ego）
- `seed_speed` — 横向 / env
- 碰撞 early-exit：`_verdict.freeze_actors`

`src/lib/_spawn.py` **只 re-export**。

### 导入门禁（防串改）

| 谁 | 可 import |
|----|-----------|
| `layouts/closing.py` | `closing_toward_lead` / `closing_along_heading` / `closing_along_pose` |
| `layouts/vru.py` | **仅** `closing_along_heading` |
| `layouts/follow_straight.py` | **仅** `release_only` |
| 其它速度 IC layout | `seed_speed` 等 |
| `run_cases.py` | **仅** `spawn.boundary.sanitize_keep_ego` |
| `AtomCase` | 可 `sanitize_keep_ego`；**禁止** `spawn.ic` |
| `place` / `pick` | **禁止** ic / boundary |

验收：

```bash
cd carla_scenarios && bash scripts/check_spawn_import_gate.sh
```

全量批跑时：静态依赖靠 import 隔离；同进程世界状态靠 `boundary.sanitize_keep_ego`。Combo 只 import 用到的 layout 阶段，阶段切换显式 sanitize + 下一阶段自己的 ic profile。

**IC 实现注意**：CARLA `enable_constant_velocity` 为**车体局部坐标**（`(+speed,0,0)` 前进）；勿把世界系速度矢量直接塞进该 API（曾导致 ACC→AEB 倒车）。

### 本轮已做 / 已知未完

已做：

- spawn 拆层 + layouts 显式组合；acc/aeb 收进 AtomCase
- boundary 案间消毒（失败销毁 hero）；place 落位后静止
- 具名 IC；门禁脚本；仪表/交通/Town/时长等环境旋钮（见 `carla.env`）
- 碰撞 early-exit 时 `freeze_actors`（停冲；无 Giraffe 时撞上仍会刹停）

已知问题（后续再开，优先 frame_ingest）：

- 无 Giraffe 时批跑大量 `exit=1`（`no_giraffe_control`）属预期，勿与布景失败混淆
- VRU / 路口横穿观感、碰撞判定阈值、环境车干扰仍需打磨
- 前车驻停刹 / 案间 sanitize 短刹 / 碰撞 freeze 会造成「有刹车」观感，并非 ego AEB 决策
- destroy actor not found 已尽量吞掉，CARLA 底层偶发日志仍可能出现
- 其它域（lateral / weather / isp…）批量验收未作为本轮关闭条件

### 分类重构 / 增减合并

| 变更类型 | 动哪里 | 不动哪里 |
|----------|--------|----------|
| 只改产品分类 | 挪 `cases/.../script.py`；改两处 manifest；根 suite `children` 若改域名 | `spawn.*`、layout 函数体 |
| 新增同类 atom | 薄 script + manifest 一行；复用 layout + ic | 其它 case；pick/place |
| 新增新布景/新 IC | 新 layout ± 新 `ic.xxx` + case + manifest | 旧 ic 默认；无关 layout |
| 合并 / 拆分 case | script + manifest 行；布景可收/fork layout | spawn 内核 |
| combo 增减阶段 | 只改 combo script 的 import/编排/handoff | atom layout 默认行为 |

**工作量预期**：增减合并小；分类重构中等但机械（mv + manifest）；真改物理只动对应 layout，怕牵连则 fork 函数名。

**Checklist**：① 决定只挪产品目录还是连 layout 族一起拆 ② `mv` script + 更新源/目标 manifest 与根 suite ③ `rg` 旧路径/旧 layout 符号 ④ 不改 `spawn/{pick,place,ic}` 除非真改物理/IC ⑤ 烟测单 case + 所属域批跑。

## 怎么跑

```bash
cd carla_scenarios
python3 run_cases.py cases/longitudinal
python3 run_cases.py cases/weather
python3 run_cases.py --no-window cases/longitudinal
python3 cases/longitudinal/acc.py          # 单 case；不写 results/
```

### 与 gf-config 相机契约对齐

compose 后 SKU 写出 `generated/camera_contract.json`（槽位 / 分辨率 / pixel / mount）。场景机**只读**该文件，无需拷进本目录：

```bash
export GF_PROJECT_DIR=/path/to/projects/afc
# 或：export GF_CAMERA_CONTRACT=$GF_PROJECT_DIR/generated/camera_contract.json
python3 cases/longitudinal/acc.py
```

详见 [frame_ingest_roles.md](./frame_ingest_roles.md)「与 carla_scenarios 同步」。

- 批跑目标只接受带 `manifest.yaml` 的目录。  
- 默认旋钮在 **`carla.env`**；CLI 可覆盖。常用：  
  - `GF_SCENARIO_DURATION_S=8`（多数 case）  
  - `GF_SCENARIO_DURATION_ISP_S=25`（隧道 / ISP，进出需要更长）  
  - `GF_CARLA_TOWN=Town04`（连上后可选切图；与 UE 是否先开该图无关；空=保持当前图）  
  - `GF_TRAFFIC_NUMBER=18`（任意滚动 5 秒窗口约新出现 N 辆进 see-cone；同时约 N/2；本车道考场窗空；0 关）  
  - `GF_SCENARIO_WRITE_RESULTS=1`（批跑是否写 `results/` 报告；默认开；`0` / `--no-results` 关）  
- `GF_SCENARIO_STOP_ON_FAIL=0` 失败继续；`=1` / `--stop-on-fail` 遇首个 fail 停。  
- AEB 族：碰撞 early-exit fail。  
- 无 SIL → `no_giraffe_control`（exit 1）；infra → exit 2。

## 结果（仅 run_cases）

见 `carla_scenarios/results/README.md`：`results/runs/<YYYYMMDD_HHMMSS>/summary.json` + `cases/<id>.json`。

## 仪表（pygame）

- 全画幅半透明 **顶栏 + 底带**（v3）：  
  - 顶栏：`i/N keyword·id` · `t / T s`  
  - 底带：车速 · SET · TGT · gap / th / TTC · **SIG**（红/黄/绿+距离）· **PED** · LIM · yaw · CTRL  
- 空槽画 `--`。不按 case 换皮。SIG 来自 CARLA 灯（绿也显示；FCM 仍只打包红/黄）。  
- **CTRL**：有控车 **绿闪**；无信号 **红闪**。  
- 不上仪表：fps、相机安装、fov、CAM。  
- 无 View 按钮；键盘 `V` 仍可静默切换 ChaseCam。

## 覆盖域

| 目录 | 内容 |
|------|------|
| `longitudinal/` | ACC / cut-in / AEB 族 / FCW / ISA |
| `lateral/` | LKA / LDW / ELK / LCC |
| `perception/` | TSR |
| `lighting/` | HLB |
| `roadway/` | lane split / merge |
| `isp_env/` | tunnel；眩光将收敛至此 |
| `weather/` | sun / rain / fog / dusk / night / wet / snow |

## 判定契约

| 项 | 约定 |
|----|------|
| scenario | 布景 + IC；禁止连续控 ego |
| ego | 仅 Giraffe→bridge |
| 无 SIL | fail `no_giraffe_control` |
| exit | `0` pass / `1` fail / `2` infra |

## 待办摘要

- 域收敛（眩光类 → `isp_env`）；按 **case 覆盖度** 取景，不绑「村庄↔日照」之类假关联  
- 场景干净 = 少杂物、布景服务 case；环境车是正常的（非 FPS）  
- FPS / 时间片：已记 [host_fps_sil_hil.md](../../../driving/host_fps_sil_hil.md)；P 与 perc 1:1，不抽帧换 Hz  
- planning 真 SET；横向 lat-offset / HLB 真 beam 决策  
- results 写入更完整的 VERDICT 字段（reason 等）
