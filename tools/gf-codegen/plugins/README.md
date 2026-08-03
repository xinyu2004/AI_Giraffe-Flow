# gf-codegen plugins

文档槽位（实现在 `src/gf_codegen/`，非独立可装包）：

| 能力 | CLI | Role |
|------|-----|------|
| import | `gf-codegen import` | OEM ARXML/FIDL/hpp → 进 compose |
| lint | `gf-codegen lint` | SOR validation gate before generate |
| generate | `gf-codegen generate` | SOR → Proxy/Skeleton、manifests、bindings |

Single binary: `gf-codegen`.

Parent: [../README.md](../README.md)
