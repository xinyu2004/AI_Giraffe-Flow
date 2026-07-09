```text
gf-codegen compose --project <project.yaml>   # integrator: one-shot → gf.sor.json
gf-codegen lint [--lineage] ...
gf-codegen generate ...
```

## 集成工程师（一句话）

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```

内部：OEM import + hpp 内存解析 + wiring 合并 + lineage 检查。**模块侧不产出 JSON**。

## 模块工程师

只维护 `io_types.hpp`。见 [Requirement/modules/](../../Requirement/modules/)。

## 文档

[sor-authoring.md](../../docs/zh/architecture/sor-authoring.md) · [projects/](../../projects/)

Plugins: [plugins/](plugins/)（待实现）
