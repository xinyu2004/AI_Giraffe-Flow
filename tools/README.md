# tools/ (host only)

| Tool | Role |
|------|------|
| [importer](importer/) | ARXML / DBC / YAML → `gf.sor.json` |
| [codegen](codegen/) | SOR → `gf_ara` Proxy/Skeleton, manifests, binding configs |
| [architect](architect/) | DAG viewer + signal lineage review |
| [record_replay](record_replay/) | Long-horizon record / replay |
| [lint](lint/) | SOR lint (cycles, dangling requires, unmapped OEM signals) |

Must **not** be linked into production onboard images. See `deps/` board_build_excludes.
