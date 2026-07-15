# Giraffe Measure Tool (GMT)

Host-only tools for **architecture review (CI)** and **measurement export**.

| 入口 | 说明 |
|------|------|
| **信号链接 / SKU 编辑** | **`gf-config`** — 唯一作者 GUI（**无 GMT 窗口**） |
| `GMT architect lineage` | CI 只读：跑 SOR lineage，失败非 0 |
| `GMT architect dag` | 打印 process/dataflow JSON（无 GUI） |
| `GMT measure export` | JSONL session → **MCAP 雏形**（无 Foxglove 桥；P2 深化） |

```bash
pip install -e tools/gmt -e tools/codegen
# 人工：gf-config 保存（自动 Compose）；CI：
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
GMT architect lineage --project projects/oem_a/afc_with_uss/project.yaml
GMT measure export --in tools/gmt/fixtures/session_stub.jsonl --out /tmp/out.mcap
bash scripts/smoke_ta.sh
```

CLI 入口名：**`GMT`**（小写 `gmt` 仍为兼容别名）。Python 包名仍为 `gf_gmt`（语言惯例）。

**Not in GMT:** OEM import、SOR lint、codegen、可写连线 — 见 **`gf-codegen`** / **`gf-config`**。  
ARXML 子集：`gf-codegen import arxml`（可接 FARACON 产出）。

Plugins: [plugins/](plugins/). Legacy：`tools/architect`、`tools/record_replay`。

Parent: [tools/README.md](../README.md)
