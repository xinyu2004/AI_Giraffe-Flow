# ADC — 空槽（未开工）

行泊一体 SKU **占位**。AFC 做完再从 `projects/afc` 复制 `apps/` / `compile_sil` / `run_sil`，再加环视、泊车、MCU。

**不要**从旧 wiring（USS / 泊车假模块）长出来；那些已清掉。

```bash
python -m gf_codegen.compose --project projects/adc/project.yaml
gf-codegen lint projects/adc/gf.sor.json
```

iceoryx / MCU IPC 烟测在 `middleware/bindings/`，不在本目录。
