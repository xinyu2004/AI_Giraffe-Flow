# Giraffe Measure Tool (GMT)

Host-only tools for **architecture review (CI)** and later **measurement**.

| 入口 | 说明 |
|------|------|
| **信号链接 / SKU 编辑** | 在 **`gf-config`**（[`../config/`](../config/)）— **唯一作者 GUI**；architect GUI 已迁走 |
| CLI（计划） | `gmt architect dag\|lineage` — CI / 无显示器，**只读** SOR / lineage |
| measure / bridge | P1 后半～P2（MCAP / Foxglove）；读运行数据，**不写回 SOR** |

**Not in GMT:** OEM import、SOR lint、codegen、可写连线画布 — 见 **`gf-codegen`** / **`gf-config`**。

Plugins: [plugins/](plugins/)（骨架）。Legacy：`tools/architect`、`tools/record_replay`。

Parent: [tools/README.md](../README.md)
