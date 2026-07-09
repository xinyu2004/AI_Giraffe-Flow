# Giraffe Measure Tool (GMT)

Host-only unified CLI for **measurement and analysis** after the build contract is fixed.

```text
gmt architect dag|lineage ...    # design-time: read SOR
gmt measure record|tag|export|replay|trace2vcd|plot|bench ...
gmt bridge foxglove|ros-graph|play ...
```

**Not in GMT:** OEM import, SOR lint, code generation — those live in **`gf-codegen`**.

Plugins: [plugins/](plugins/) (skeleton). Legacy dirs `tools/architect`, `tools/record_replay` map here.

Parent: [tools/README.md](../README.md)
