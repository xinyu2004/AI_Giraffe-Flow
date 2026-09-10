# sm — Function Group state machine

| API | Role |
|-----|------|
| `EnsureGroup` / `RequestTransition` | **machine** FG：Off ↔ Running ↔ Updating |
| `EnsureGroupNamed` / `RequestTransitionNamed` | **mode** FG：任意态名字符串 |
| `PublishFgState` / `ReadFgState` | 跨进程 FgStateStore（按 `fg_id`）；Named 切态后自动 Publish |
| `NotifyHealthFault` | PHM hook；仅对 machine FG 可选进 Updating |

In-process table（进程内）+ POSIX shm `/gf_ara_fg_state`（跨进程，EM set-diff）。

产品态名（DrivingActive / EmbActive…）**不**在本中间件定义。

## ModeDeclaration 差集（EM）

```text
Mode App → RequestTransitionNamed(fg_id, state)
        → PublishFgState(fg_id, state)
EM Poll  → for each process with active_in:
             want = (ReadFgState(function_group) ∈ active_in)
           → Spawn / Terminate
```

## Boot order

```text
EM StartAll → seed mode FG initials from freeze → hold-off non-members
apps bring-up → machine: EnsureGroup(Running); mode FG: skip enum Ensure
Mode App → EnsureGroupNamed + RequestTransitionNamed
```

Smoke: `gf_sm_fg_smoke`（多 FG Publish/Read + machine 非法迁移）。  
Machine/PHM SIL：`smoke_sil_sm_fg.sh`（**不是**差集验收）。  
差集：`gf_em_fg_setdiff_smoke` + ADC `smoke_sil_drive_park_fg.sh`。

Parent: [middleware/README.md](../README.md)
