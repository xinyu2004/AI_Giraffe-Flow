# Repository layout

Monorepo **skeleton** (headers + docs; runtime/tools implementation in P0+).

```text
AI_Giraffe-Flow/
  projects/             # OEM/产品：DBC + interfaces + wiring + req + golden
  tools/codegen/        # gf-codegen（Python≥3.10）：compose/lint/suggest/generate
  schemas/              # gf.sor.json contract + examples
  middleware/           # Board runtime（P0 轨 B 待实现 iceoryx 闭环）
  platform/ bindings/ bridge/ apps/ deploy/ deps/ docs/
```

## Toolchain flow（当前）

```text
project → gf-codegen compose → gf.sor.json → lint/lineage → golden
         → generate（目前仅 types hpp）→（下一步）Proxy/Skeleton + iceoryx demo
```

上传前见：[projects/UPLOAD_CHECKLIST.md](projects/UPLOAD_CHECKLIST.md)

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

Links: [README.md](README.md) · [projects/](projects/) · [deps/README.md](deps/README.md)
