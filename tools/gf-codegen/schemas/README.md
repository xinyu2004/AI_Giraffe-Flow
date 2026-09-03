# tools/gf-codegen/schemas/

**SOR (Statement of Requirements)** contract lives with gf-codegen (lint / compose consume this, not a repo-root package).

| File / dir | Status | Purpose |
|------------|--------|---------|
| `gf.sor.schema.json` | **stub** | JSON Schema for `gf.sor.json` |
| `examples/` | placeholders | Minimal SOR examples for lint/codegen golden tests |
| `CHANGELOG.md` | stub | Schema semver notes |

`gf-codegen lint` validates SOR instances against `gf.sor.schema.json`. Compose `base` defaults to `examples/desktop_ap_only.sor.json`.
