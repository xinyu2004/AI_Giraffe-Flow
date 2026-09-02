# tools/

Host toolchain around the SOA centre. **Never ship** host GUIs on production board images. Board-side GMT probes live in [gmt_board/](gmt_board/).

## Products（职责不交叉）

| Binary / dir | Dir | 职责 | 不做 |
|--------|-----|------|------|
| **gf-config** | [gf-config/](gf-config/) | **唯一作者 GUI**：SKU + 信号图；**保存自动 compose**；可选 **Generate** | 不做 runtime 观测 |
| **gf-codegen** | [gf-codegen/](gf-codegen/) | CLI：`lint` · `suggest` · `generate` · `emit-idl` · `import`；compose 仅作库 | **无 GUI** |
| **gf-octavecoder** | [gf-octavecoder/](gf-octavecoder/) | `.m` 金源 → C 1:1（规划） | 不改算法语义 |
| **GMT** | [gmt/](gmt/) | 主机：architect CI + measure / JSONL Foxglove 回放 + GUI / OTA | 不 import、不 generate、不回写 SOR |
| **gmt_board** | [gmt_board/](gmt_board/) | 板端/SIL：tap · inject · `gf_foxglove_ws` | 不上 Python |

> 信号链接 GUI 在 **gf-config**。`gf-config` 调用 `gf_codegen.compose` 属于库依赖。公开 CLI **无** `gf-codegen compose`。

```text
人工：gf-config 编辑 → 保存（自动 compose）→ Generate（可选）→ compile_sil
CI：  python -m gf_codegen.compose → gf-codegen generate → cmake / devops/ci
观测：C gf_foxglove_ws :8765 · GMT measure / gui · inject
```

**Never ship** host tools on production board images.

CLI：`GMT architect …` / `GMT measure …` / `GMT gui`（`gmt` 为别名）。

曾用过的空壳目录 `architect/` · `lint/` · `importer/` · `record_replay/` · `bridge/` · `gmt/plugins/` 已删除；能力分别在 **GMT** / **gf-codegen** / **gmt_board**（Foxglove 直播）。ROS 2 仍走 DDS 直连，不另开桥目录。
