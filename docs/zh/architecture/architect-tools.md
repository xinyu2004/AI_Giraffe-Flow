# 架构师工具

> 设计意图：[DESIGN.md §5 / §8](DESIGN.md) · 工作流：[WORKFLOW.md §10](../operations/WORKFLOW.md) · **P2.5：** [P2_5_PLAN.md](../operations/P2_5_PLAN.md)

| 能力 | 落点 |
|------|------|
| 设计期拓扑真图 | **gf-config 页 1 画布**（无独立 DAG 页） |
| Graphviz `.dot`/SVG | gf-config 导出；或 `GMT architect dag --format dot` |
| Lineage | gf-config 页 1 右侧 + `GMT architect lineage` |
| 录制 / 可编辑 Tag / 主机回放 | **`GMT gui`** + `GMT measure …` |
| 动画 DAG / 先后竞态 | GMT GUI（同一时间轴） |
| Foxglove | `GMT bridge foxglove`（live 或 JSONL） |
| DoIP / UDS 操作 | GMT **OTA/UDS**（OTA · DEM-lite · Collector；配置在 gf-config） |
| 中间件回灌（G3） | **`gf_iox_obs_inject`** + GMT「回灌」页（playhead）；禁止双发布 |

## 产品顺序

```text
gf-config → Verify/Generate/compile → run_sil
  → GMT gui（录制 / Tag / scrub / Live / OTA·UDS）
  →（可选闭环）GF_INJECT_MODE=playhead → GMT 回灌页连 :8767
```

## GMT GUI

```bash
GMT gui --project projects/oem_a/afc_with_uss \
  --session build/observability/session.jsonl
```

Tag 持久化：`session.tags.json`（可改名/改窗/topics/备注）。

## 回灌

见 [iox_obs_inject README](../../../tools/debug_bridge/iox_obs_inject/README.md)：

- **拓扑 B1/B2**：`run_sil` 决定起哪些进程  
- **灌法 continuous / playhead**：playhead 时 inject 等 GMT seek（tcp:8767）  
- **旁观**：回灌时可同时连 Live（ws:8766）；默认只订下游；「跟 playhead」时 GUI 关 Live 跟随  
