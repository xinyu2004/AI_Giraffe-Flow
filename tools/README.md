# tools/

## Three products（职责不交叉）

| Binary | Dir | 职责 | 不做 |
|--------|-----|------|------|
| **gf-codegen** | [codegen/](codegen/) | CLI：`lint` · `suggest` · `generate` · `emit-idl` · `import`；compose 仅作库 / `python -m gf_codegen.compose` | **无 GUI** |
| **gf-config** | [config/](config/) | **唯一作者 GUI**：SKU + 信号图；**保存自动 compose**；可选 **Generate** | 不做 runtime 观测 |
| **GMT** | [gmt/](gmt/) | 只读 architect（CI）+ measure / bridge（P1+） | 不 import、不 generate、不回写 SOR |
| **bridge** (host) | [bridge/](bridge/) | optional ROS 2 helpers | — |

> 信号链接 GUI **已迁到 gf-config B 页**（不再放在 GMT architect）。`gf-config` 调用 `gf_codegen.compose` 属于库依赖，不是工具交叉使用。公开 CLI **无** `gf-codegen compose`。

```text
人工：gf-config 编辑 → 保存（自动 compose）→ Generate（可选）→ build
CI：  python -m gf_codegen.compose → gf-codegen generate → cmake
Analysis → GMT measure / bridge（只读 / 运行数据）
```

## Legacy directories

| Legacy | Maps to |
|--------|---------|
| [importer/](importer/) | codegen/plugins/import |
| [lint/](lint/) | codegen/plugins/lint |
| [architect/](architect/) | gmt/plugins/architect（CLI；GUI → gf-config） |
| [record_replay/](record_replay/) | gmt/plugins/measure |

**Never ship** host tools on production board images.

CLI：`GMT architect …` / `GMT measure …`（`gmt` 为别名）。
