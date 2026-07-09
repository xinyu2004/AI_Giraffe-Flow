# tools/

## Two products

| Binary | Dir | Commands |
|--------|-----|----------|
| **gf-codegen** | [codegen/](codegen/) | `import` · `lint` · `generate` |
| **GMT** (Giraffe Measure Tool) | [gmt/](gmt/) | `architect` · `measure` · `bridge` |

```text
OEM → gf-codegen import → lint → generate → build
Analysis → gmt measure / bridge / architect
```

## Legacy directories

| Legacy | Maps to |
|--------|---------|
| [importer/](importer/) | codegen/plugins/import |
| [lint/](lint/) | codegen/plugins/lint |
| [architect/](architect/) | gmt/plugins/architect |
| [record_replay/](record_replay/) | gmt/plugins/measure |

**Never ship** host tools on production board images.
