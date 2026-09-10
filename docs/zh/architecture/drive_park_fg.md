# ModeDeclaration Function Group 差集（通用）+ ADC DrivePark 示例

> 中间件只认识：**FG id、kind、态名字符串、进程 `active_in`**。  
> 产品词（DrivingActive / EmbActive / …）只留在 App 与作者 YAML，不进 SM/EM API。

## 两把尺（FG 模型）

| kind | 态 | 谁 Ensure | EM |
|------|----|-----------|----|
| `machine` | Off / Running / Updating | bring-up `EnsureGroup(Running)` | 常驻（无 `active_in`） |
| `mode` | 任意 ModeDeclaration 名 | Mode/OEM App `EnsureGroupNamed` / `RequestTransitionNamed` | `want = (ReadFgState(fg) ∈ active_in)` |

跨进程 desired：`StateClient::PublishFgState` / `ReadFgState`（POSIX shm `/gf_ara_fg_state`，按 `fg_id` 分槽）。

## 作者面（exec.yaml）

```yaml
function_groups:
  - id: MachineFG
    kind: machine
    initial: Running
  - id: DriveParkFG          # 名字任意；OEM 可 EmbFG / ChassisFG
    kind: mode
    states: [DrivingActive, ParkingActive]
    initial: DrivingActive
processes:
  - name: planning.driving
    function_group: DriveParkFG
    active_in: [DrivingActive]
  - name: planning.parking
    function_group: DriveParkFG
    active_in: [ParkingActive]
```

禁止：`drive_park_state`；EM 按进程名硬编码。

## ADC 示例：DriveParkFG

| 进程 | FG | active_in |
|------|----|-----------|
| perception.* / mode / gateway | MachineFG | （空＝常驻） |
| planning.driving | DriveParkFG | DrivingActive |
| planning.parking | DriveParkFG | ParkingActive |

Mode Manager（`mode.drive_park`）持有产品常量，调用：

`RequestTransitionNamed("DriveParkFG", DrivingActive|ParkingActive)`。

切态时 EM：**终止**不在目标集合的规划进程，**拉起**进入集合的规划进程。

## 谁发起（ADC）

```text
停稳 + slot_confirmed → ParkingActive
否则（含 SpotSearch v<15）→ DrivingActive
```

Gateway：**纯转发**存活侧 traj（不做 Mode 选源）。

## 环境

| 变量 | 作用 |
|------|------|
| `GF_SLOT_CONFIRMED` / ModeHint cosim | 确认进泊（停稳后） |
