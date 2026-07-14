# tools/

## Three products（职责不交叉）

| Binary | Dir | 职责 | 不做 |
|--------|-----|------|------|
| **gf-codegen** | [codegen/](codegen/) | CLI：`compose` · `lint` · `suggest` · `generate` | **无 GUI** |
| **gf-config** | [config/](config/) | **唯一作者 GUI**：SKU + 信号链接画布 → 写 `req.yaml` / `wiring.yaml` | 不写 `gf.sor.json`；不做 runtime 观测 |
| **GMT** | [gmt/](gmt/) | 只读 architect（CI）+ measure / bridge（P1+） | 不 import、不 generate、不回写 SOR |
| **bridge** (host) | [bridge/](bridge/) | optional ROS 2 helpers | — |

> 信号链接 GUI **已迁到 gf-config B 页**（不再放在 GMT architect）。`gf-config` 调用 `gf_codegen.compose` 属于库依赖，不是工具交叉使用。

```text
OEM → gf-codegen compose → lint → generate → build
集成连线 → gf-config（图）→ compose / lineage
Analysis → gmt measure / bridge（只读 / 运行数据）
```

## Legacy directories

| Legacy | Maps to |
|--------|---------|
| [importer/](importer/) | codegen/plugins/import |
| [lint/](lint/) | codegen/plugins/lint |
| [architect/](architect/) | gmt/plugins/architect（CLI 骨架；GUI → gf-config） |
| [record_replay/](record_replay/) | gmt/plugins/measure |

**Never ship** host tools on production board images.
