# SOR authoring (simplified)

> **中文:** [sor-authoring.md](../../zh/architecture/sor-authoring.md)

## Roles

| Role | Delivers | Does NOT deliver |
|------|----------|------------------|
| Module engineer | `io_types.hpp` | JSON fragments, wiring, SKU |
| System integrator | `projects/<oem>/<vehicle>/` OEM DBC, wiring, `req.yaml` | — |
| DevOps | `req.yaml` acceptance, CI gates | Wiring details |

## Four inputs + one entry

| Input | Owner |
|-------|-------|
| `io_types.hpp` | Module engineer |
| `oem/oem_import.dbc` | Integrator |
| `integration/wiring.yaml` | Integrator |
| `req.yaml` | Integrator + DevOps |
| `project.yaml` | **Index only** — paths + compose output |

## One command

```bash
gf-codegen compose --project projects/afc/project.yaml
```

Tool internally: parse hpp + import oem + apply wiring + merge req → `gf.sor.json` + lineage report.

Examples: [projects/afc/](../../../projects/afc/) · [interfaces/](../../../projects/afc/interfaces/)
