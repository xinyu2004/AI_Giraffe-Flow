# gf-octavecoder — 分阶段计划（现行）

> 状态：SKU 目录已迁至 `projects/afc` / `projects/adc`。  
> 与 **`gf-codegen` 零耦合**。产品通信终态：iceoryx + GfChannel（本计划 Phase 1 **不**砍 JSON）。

## 已拍板

| 项 | 决定 |
|----|------|
| 生成落点 | `projects/<sku>/apps/planning/driving/oct_gen/`（gitignore；**不**经 `generated/octave` 再拷贝） |
| Phase 1 算法 | 先纵向 ACC/AEB；横向 Phase 2 |
| JSON 去控车 | ✅ Phase 3：`Trajectory` 带 thr/brk/steer；gateway 不读 `planning_ctrl.json` |
| BEV | 前 120/130 m，后 60 m |
| AFC USS | 无 |

## 设计原则（强制）

### 1. 独立函数 + 算法一一对应

- **关注点拆成独立函数**（例：CARLA 驻车/手刹、限速、夹紧、跟车 gap、AEB 触发）——便于复用与单测，禁止一锅粥。
- **Octave `.m` = 该算法的权威表述**；转译/手写 C（`oct_gen` 或 `ops`）是**对应实现**，接口与语义对齐，禁止「.m 一套、C 另一套」。
- **编排进 ops 手写**：网格、优先队列、IPM/LUT、与中间件强绑定的 I/O 不适合作 `.m` 子集时，放 `gf_octave_planning`，由 `.m` 调用白名单入口。

### 2. 切忌按下葫芦浮起瓢

- **单点变更**：一次只迁一个算法面（先 clamp 骨架 → 再纵向 → 再横向）。
- **金向量门禁**：每个抽出的函数有固定输入/输出；CI 红则回退该点，不连带大改 gateway / BEV / EM。
- **产品路径不动**：`run_sil` 不引入故障注入；Phase 3 起控车走 iceoryx `Trajectory` → GfChannel `vehicle_cmd` → cosim（无 `carla_cmd.json`）。
- **可回退**：薄壳保留旧路径开关或短时 `#if` 仅在抽取窗口；合并前必须默认走新路径且绿。

## 阶段

| 阶段 | 内容 | 验收 |
|------|------|------|
| **0** | 合同/README 对齐（本文件 + 目录 README） | ✅ 路径与原则无歧义 |
| **1a** | CLI 骨架、CMake 链 `ops`+`oct_gen`、`gf_clamp` 金向量 | ✅ generate + pytest；`compile_sil` 调 sync |
| **1b** | 纵向 ACC/AEB → `.m` → `oct_gen`；薄壳只调入口 | ✅ 独立函数 + 金向量；steer 仍在薄壳 |
| **2** | 横向 LKA + 定长轨迹（独立函数） | ✅ `m_lat_lka` / `m_lat_traj` + 金向量 |
| **3** | gateway 去 JSON 控车 | ✅ 控车字段进 iceoryx `Trajectory`；egress GfChannel `vehicle_cmd` + cosim；无 `planning_ctrl.json` / `carla_cmd.json` |
| **4** | 环视/A*、HIL | 另开任务 |

## 目录合同（现行）

```text
octave_planning/{afc,adc,common}/*.m     ← 仅金源
tools/gf-octavecoder/
  ops/          ← gf_octave_planning（手写，上板链接）
  （CLI/转译器）
projects/afc/apps/planning/driving/
  src/main.cpp  ← 薄壳 iceoryx
  oct_gen/      ← 生成物（直接写出）
→ 二进制 gf_planning_driving
```

## L0 转译子集（Phase 1）

允许：标量、`if/else`、调用白名单（如 `gf_clamp`）、简单算术、定长小循环。  
禁止：plot、文件 I/O、cell、eval、动态尺寸矩阵滥用、OOP。
