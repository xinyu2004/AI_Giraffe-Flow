# tools/

## Three products（职责不交叉）

| Binary | Dir | 职责 | 不做 |
|--------|-----|------|------|
| **gf-config** | [gf-config/](gf-config/) | **唯一作者 GUI**：SKU + 信号图；**保存自动 compose**；可选 **Generate** | 不做 runtime 观测 |
| **gf-codegen** | [gf-codegen/](gf-codegen/) | CLI：`lint` · `suggest` · `generate` · `emit-idl` · `import`；compose 仅作库 / `python -m gf_codegen.compose` | **无 GUI** |
| **GMT** | [gmt/](gmt/) | 只读 architect（CI）+ measure / bridge（P1+）+ OTA | 不 import、不 generate、不回写 SOR |

可选占位（无实现、不上板）：

| Dir | 意图 |
|-----|------|
| [bridge/](bridge/) | 主机侧 ROS 2 辅助（优先 DDS 直连；与 GMT 内 Foxglove bridge 不同） |

> 信号链接 GUI 在 **gf-config**。`gf-config` 调用 `gf_codegen.compose` 属于库依赖。公开 CLI **无** `gf-codegen compose`。

```text
人工：gf-config 编辑 → 保存（自动 compose）→ Generate（可选）→ build
CI：  python -m gf_codegen.compose → gf-codegen generate → cmake
观测 / OTA：GMT measure · bridge foxglove · OTA（DoIP）
```

**Never ship** host tools on production board images.

CLI：`GMT architect …` / `GMT measure …` / `GMT gui`（`gmt` 为别名）。

曾用过的空壳目录 `architect/` · `lint/` · `importer/` · `record_replay/` 已删除；能力分别在 **GMT** / **gf-codegen**。
