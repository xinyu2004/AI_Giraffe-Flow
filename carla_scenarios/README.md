# carla_scenarios

CARLA Client A — AFC 场景套件（布景 + IC；连续控车应走 Giraffe→bridge）。主机侧压力源，不是控制器。

**文档（架构 / 分层 / Session策略 / 可见性准则 / 门禁 / 已知问题）：**

- 中文：[docs/zh/sku/afc/scenarios.md](../docs/zh/sku/afc/scenarios.md)（含 **Session/env 分层** 与 **禁止 see-cone 内突然刷出**）
- English：[docs/en/sku/afc/scenarios.md](../docs/en/sku/afc/scenarios.md)
- Cursor 规则：`.cursor/rules/carla-scenarios.mdc`（改本树前先读）

```bash
cd carla_scenarios
python3 run_cases.py cases/longitudinal   # batch → results/runs/<ts>/
python3 run_cases.py cases/longitudinal/manifest.yaml
python3 cases/longitudinal/acc.py         # single case (no results/; ends with cleanup)
bash scripts/check_spawn_import_gate.sh   # spawn import 门禁
```

### 批跑自然续场（`run_cases.py`）

- 入口只接 **带 manifest 的目录** 或 **manifest 本身**。
- **同一 Client / 同一 pygame 窗口**；案间 `preserve_ego=1` **不销毁 hero**。
- 若世界里已有 hero → `keep_ego=1` 续位姿只改布景；没有则冷启动 spawn（首案或意外丢车）。
- **可不接 Giraffe**：布景链仍可跑；无控车时 judge 常报 `no_giraffe_control`（exit=1）属预期，不等于场景机挂了。
- **冷启动**：每次 `run_cases` **仅开局**清掉 UE 残留 hero；案 2+ 只要 hero 还活着就续用（车头歪也不重开窗 / 不换车）。
- **丢车**：仅 mid-batch hero 消失/死亡才冷启动（可能重挂视角）。
- 单跑脚本仍一案结束清场 — 连续 demo 请用批跑。

Defaults: `carla.env`。实现：`src/spawn` + `src/layouts` + `src/lib`。产品案：`cases/`（manifest 只列清单）。

**上位机相机**：`GF_CAMERA_CONTRACT=afc` → `config/afc/camera_contract.json`（compose/Verify 导出；**不用** `GF_PROJECT_DIR`）。详见 [config/README.md](config/README.md)。
