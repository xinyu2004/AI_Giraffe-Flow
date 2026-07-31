# middleware/

Board-deployable packages. Public API: `gf_ara::*`; internals: `gf::*`.

Enable subsets per SKU via SOR / `req.yaml` `runtime_modules[]`.

**与架构 GIF SoC 芯片对齐**（`result_pic/architecture_flow*.gif`）：

| GIF 芯片 | 本目录包 | 说明 |
|----------|----------|------|
| com | [com](com/) | 统一通信 |
| EM | [exec](exec/)（EmDaemon） | OSAL Spawn / relaunch |
| exec | [exec](exec/) | ExecutionClient |
| phm | [phm](phm/) | Alive / Deadline / Logical |
| sm | [sm](sm/) | Function groups |
| collector | [collector](collector/) | 事件环 / DEM-lite |
| OSAL | [osal](osal/) | 时钟 / 线程 / **process** |
| diag | [diag](diag/) | DoIP 会话（TCP）+ UDS Routine → OTA |
| ucm | [ucm](ucm/) | PackageManager + OtaOrchestrator（SIL） |
| log | [log](log/) | 日志 lite |
| per | [per](per/) | 持久化 KV stub（可裁剪） |
| tsync | [tsync](tsync/) | 时间同步骨架（可裁剪） |

另有： [core](core/) · [bindings/](bindings/) · [hal](hal/) · [trace](trace/)（偏 debug-path）· [third_party/](third_party/)。

| Package | Role | Phase |
|---------|------|-------|
| [core](core/) | Result / ErrorCode | P0 |
| [com](com/) | Unified communication API | P0 |
| [bindings/](bindings/) | Transport plugins (iceoryx / someip / dds …) | P0+ |
| [osal/](osal/) | OS abstraction (clock / thread / **process**) | P0 |
| [hal/](hal/) | Board sensors / actuators | P1+ |
| [third_party/](third_party/) | Upstream checkouts (gitignored) | P0+ |
| [exec](exec/) | ExecutionClient + **EmDaemon** (OSAL Spawn) | P3 |
| [phm](phm/) | Platform health (`notify_sm` / restart→EM) | P3 |
| [sm](sm/) | Function groups Off/Running/Updating | P3 |
| [collector](collector/) | Event collector (DEM-lite / cp_dem stub) | P3 |
| [log](log/) | Logging lite（stdout/stderr） | P3 |
| [per](per/) | Persistency KV stub（可裁剪） | P3 |
| [tsync](tsync/) | Time sync skeleton（可裁剪） | P3 |
| [trace](trace/) | Trace → VCD / GMT | P2 |
| [ucm](ucm/) | OTA / packages + orchestrator | P3 ●（RAUC stub） |
| [diag](diag/) | DoIP TCP session + UDS subset | P3 ● |

Staging (gitignored): `middleware/.deps-prefix/` after `bash scripts/bootstrap_deps.sh`.

```bash
bash scripts/bootstrap_deps.sh
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure
# fusa (L1 CASE lines → fusa/runs/):
bash fusa/scripts/run_cases.sh
```

FuSa matrices: [fusa/cases/](../fusa/cases/) · policy: [fusa/POLICY.md](../fusa/POLICY.md).

Unit / component smokes live under each module’s **`testcases/`** directory.
