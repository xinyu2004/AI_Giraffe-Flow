# Host 帧率 / 时间片 → SIL/HIL 复用

> 规控合同仍是 [planning_lon_v4.md](./planning_lon_v4.md)。本文只记提速与时间片；**禁止用抽感知帧换 giraffe 表观 Hz**。

## 0. 合同（这次纠偏）

两条钟，不能混。**算法效果**（同一组 `m_plan_tick` 入参 → 同一 thr/brk/steer）必须一致；**传数方式**不必一致（Host 解释器 vs 板 SOA/CAN）。

| 钟 | 目标 | 允许丢吗 |
|----|------|----------|
| **W 世界** | UE 物理 ≥20 Hz | 否（日志才可信） |
| **P 感知+规划** | Host Octave：发出去的每一帧 fake_perc 都进 `m_plan_tick`（window=1）。板：每个 **Take 到的** perc 进一次 tick；overlay 盖掉未消费样本 = Error，不要用 wait 假装成队列 | 板：未 Take 的可被覆盖；已 Take 的不许丢 |
| **V 观测** | BEV / Foxglove / pygame | 可以降频、可以关 |

覆盖 latest 丢掉的是通信层未消费样本，不是再跑一遍公式。giraffe 表观 Hz ≠ 规划 Hz。

**Host 要 20 Hz 的 P，只能让一拍墙钟 < 50 ms。** 做不到就诚实跑在真实 P 上（Octave window=1），去削一拍成本。板侧 `giraffe_client` **不等 cmd**，世界钟自己走。

## 1. 已落地（Host）

| 改动 | 作用 | SIL/HIL |
|------|------|---------|
| `GF_GIRAFFE_CAM=0` | 不挂 RGB、不 Python NV12、不 `send_camera` | 规划不吃图时同样关；环视走 C++ ingest |
| Python NV12 门控 | 合同还在，默认不跑 | **禁止**把 `rgb_to_nv12` 搬上板 |
| `[perf]` 四钟 | 分清 W / P / V | 板：规划 tick、ingest、gateway；不要拿 BEV 当 MCU 钟 |
| BEV ≠ 相机 CompressedImage | Host 只发 BEV PNG | 观测归 GMT；控制环不合成图 |
| `O(traj_n × obj_n_max)` 16×8 | 算法预算钉死 | generate C 后同一上限；加刀先量一拍，超了显式改预算 |
| 只在 `FAKE_PERC` 上 `plan_tick` | 去掉 state 二次规划 | 感知更新才跑规划 |
| TCP window=1（等 cmd / 超时重发同一拍） | Host Octave：不抽 perc、不堆 `send_st` | 板 `giraffe_client`：overlay-latest，不等 cmd、不重发同一 perc |
| BEV `BevAsync` | V 可丢，P 不丢 | GMT 不进控制进程 |
| `[perf]` `plan` / `m` / `ffi` / `over_budget` | 剖 Host 税 | 板上对等 tick 墙钟 |
| `gf_plan_cal` persistent | Host 少重建 cal | C 本就是常量 |
| pygame 一路 + `GF_SCENARIO_VIEW=0` | 还 iGPU（W） | 无关板端 |
| `collect_dyn` 一次 `get_actors` + snapshot | 去掉每目标 RPC / 循环里反复取 ego | Host fake_perc 税；板上是感知输出 |
| `collect_dyn` type_id/bbox 缓存 | 首拍全量，之后只 snapshot；新 id 才补拉 | 同上 |
| lane 自车位姿一次 + `get_map` 缓存 | 采点不再每点 `get_transform` | Host fake_perc |

未改：UE `--no-window`、规控标定数字、generate。

P 的 Hz：Host 看 `[perf][octave] hz=`（window=1 时等于一拍墙钟倒数）；板看规划 `tick_ms` / Out 到达率，不要看空转 giraffe。

实测（`ipc=file`）：P 约 10Hz，`plan≈67ms` 里 `m≈16ms` + `ffi≈52ms`（Windows `pause`/文件）。Windows Octave `fopen` 打不开 `\\.\pipe\`。要到 20Hz 走 **二进制 stdio + 进程内 `_setmode`**（`gf_stdio_binmode_oct`，`auto`：stdio→file）。不要默认 TCP（JVM Socket 会段错误）。BEV 默认 5Hz。

## 2. 一拍为什么贵（剖开再削）

```text
giraffe ──TCP──► 同一线程：
                  m_plan_tick ~200ms（oct2py + .m）
                  bev PNG     ~110ms（V，不该进 P）
                  state 与 perc 各 on_tick 一次（同一场景算两遍）
```

16×8 的算术不该是 200 ms。候选税（P0 要用 `[perf]` 拆开，再动手削）：

1. **双触发**：state+perc 各跑一遍计划 → P 直接腰斩。削它**不丢 perc**。
2. **BEV 进控制线程**：~110 ms 观测税。搬走/降频只动 V。
3. **oct2py FFI**：每拍进一大表、出 struct+三条轨迹数组。
4. **`gf_plan_cal()` 每函数重建**：`m_plan_tick` 链路里十余个 `.m` 各调一次，Host 解释器税；C 里是头文件常量，无此成本。
5. **iGPU**：pygame 两路 960×540 和 UE 抢集显 → **W** 掉，不是 P 抽帧。
6. **`collect_dyn`**：已收（snapshot + 单次 actor 列表 + ego 位姿外提）。再看 `[perf][giraffe] dyn=`。

板上没有 Octave。Host 金源要能调车，P 必须自己快到 20 Hz，或诚实承认 Host 金源暂时慢于板。**禁止用抽帧把 Host 伪装成 20 Hz 规划。**

## 3. 下一步（不并行 Octave，不抽 perc）

```text
W: UE ≥20 Hz（还 iGPU）
P Host: 采样 perc → 一拍计划 → cmd → 再采样   window=1（Octave 护栏）
P 板:   giraffe 按自己的钟发真值；规划 perc 身份触发；cmd overlay-latest
V: BEV/pygame 旁路，可慢
```

加刀（变道走廊等）必须进 **同一 50 ms 预算**；塞不下就减别处或显式改 `traj_n`/`obj_n_max`，禁止再靠丢 perc。

### P0 — 已落地（不改规控标定）

验收看 **P 的 Hz 和一拍 ms**，不看 giraffe 空转 Hz。

1. **单触发**：只在 `FAKE_PERC` 上 `plan_tick`；state 只缓存。
2. **TCP window=1**：Host Octave 用 `GF_COSIM_CMD_WAIT_S` 等 cmd；板 `giraffe_client` 只把该变量当「首包 cmd 日志」，不阻塞、不重发 perc。
3. **V 离开 P**：`BevAsync` 队列 1；`--no-foxglove` 仍可做 P 基线。
4. **剖 200 ms**：`[perf][octave]` 的 `plan` / `m` / `ffi`；`gf_plan_cal` persistent。
5. **还 W**：pygame 默认一路；`GF_SCENARIO_VIEW=0` 关窗。
6. **预算闸**：`GF_PLAN_BUDGET_S=0.05`，超了记 `over_budget`。

### P1 — 绕开 oct2py（Host）

默认 Windows 走二进制 stdio（`m_plan_stdio` + `gf_stdio_binmode_oct` 进程内 `_setmode`；首次用 `mkoctfile` 编 `.oct`）。失败再 file 双 seq（禁止 `replace`/`ctl.bin`）。Octave `fopen` 不能当 Win32 named pipe 客户端。**不要**默认 TCP：Octave JVM + `java.net.Socket` 会段错误。`GF_OCTAVE_IPC=tcp` 仅作试验。Linux `auto` 仍 stdio。BEV 默认 5Hz。

### P2 — SIL/HIL（fps 探针 generate）

本拍允许 `gf-octavecoder generate` 把 v4 `m_plan_tick` 链进 `gf_planning_driving`，用来量 C 的 `tick_ms`。这不是算法签收：碰撞/CIPV/行人仍按 P3 再动 `.m` 标定。

| Host | 板 |
|------|----|
| 规划不吃图 | 无视频则不跑 ingest |
| 无 Python NV12 | C++ 写槽 |
| 每发一帧 perc 都进 `.m`（window=1） | 每个 Take 到的 perc 进 C `m_plan_tick`；跟不上 = overlay Error，不要互等 |
| V 不进控制 | GMT 在工位机 |
| 16×8 + 50 ms | 规划进程 quota；加功能先量 tick |
| 只在 perc 上规划 | C：新 perc 身份才 `m_plan_tick`；Ego 只缓存（CAN 10ms hold-last 是传数，不是另一套公式） |
| SOA 触发 | FCM：假感知变化才发 Out；gateway：Ego/In/`vehicle_cmd` **10ms hold-last**（Traj 边沿 cmd 额外一拍）；`gf_carla_io`：TCP 与 cmd 槽独立。空转 1ms yield，APP 互不等待。 |

iceoryx / GfChannel 覆盖写最新是通信合同：发送方与收通道正常。若消费跟不上到达率，未处理样本会被下一发盖掉，规划眼里少一幕。不要用互等或加长 sleep 假装成队列。

C 规划进程没有 `get_actors` / Octave unpack。剩下要避开的冗余：胖 `Perception_Out` 只 `Take` 一次、立刻抽成 ≤8 行 `PlanObj` + 车道标量；occlusion / `v_at_s` / `a_req_n` 只扫这张表，不要再走 FCM 数组。`gf_plan_cal` 在 C 里是常量，无 Host 每函数重建税。

### P3 — 再改 `.m` 标定（packing 已对齐）

碰撞 log（a_req 偏晚、CIPV hop、起步 0.72、`e_y`）等 **P 稳定且一拍有数** 再动 `.m`。P2 generate 不等于 Host 算法签收。

互证只比 **同一组 `m_plan_tick` 入参**。Host `_pack_obj` / `_pack_in` 与板 `ExtractPerc` / `HostLaneFromPerc` 已对齐：

| 项 | 合同 |
|----|------|
| 空目标 | `[]` / `nobj=0`（`_dummy_in` 的 999 只给 FFI 预热） |
| 顺序 | CIPV 先行，再其余；无 dyn 仅 lead 时合成一行（heading 用 rad） |
| 行人 | `cls==5` → `is_ped`；FCM `obj_ped` 也写成 class 5 |
| `x_end` | 公布 VR，缺则 60；不再地板 20 m |
| `lane_count` | 有效车道为 1，有 adj 为 2（`.m` 只测 `>=2`） |

**不要**把板上传数倒灌进 `.m`。Colorbar / gateway 映射表 / VehicleBus 周期仍是后续债，不在本拍。

## 4. 明确不做

- mailbox 当规划队列（覆盖 latest 丢未消费样本 = Error，不是改成 wait）。
- Octave OpenMP、第二套 `octave-cli` 抢核。
- 把 `giraffe_client` 表观 Hz 当规划 Hz。
- 为帧率先砍 `traj_n`/`obj_n_max`（除非剖面证明 `.m` 超预算）。
- 把 Host window=1 / 同快照打包改成 `.m` 的要求。
- 本拍改 gateway 映射表 / 取消同源 façade。
