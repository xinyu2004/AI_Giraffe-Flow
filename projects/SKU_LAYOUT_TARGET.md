# SKU 与 Octave 目录（已迁徙）

> 现行布局如下（已去掉 OEM 层与 `with_uss`）。

| 路径 | 说明 |
|------|------|
| `projects/afc/` | AFC 前视主干，**无 USS** |
| `projects/adc/` | ADC 行泊一体 |
| 已删除 | 旧 OEM 分层目录与双 SKU 变体命名 |

Octave / ops / 生成物合同：

- [`../octave_planning/README.md`](../octave_planning/README.md) — 仅 `.m`
- [`../tools/gf-octavecoder/README.md`](../tools/gf-octavecoder/README.md) — 转译器 + `ops/` → `oct_gen/` → `gf_planning_driving`
- [`../tools/gf-octavecoder/PLAN.md`](../tools/gf-octavecoder/PLAN.md) — 分阶段（1a 骨架 → 1b 纵向 → …）；独立函数 + 防回归
