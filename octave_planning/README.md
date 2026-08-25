# octave_planning/ — 仅 `.m` 金源

```text
afc/*.m     →  projects/afc/apps/planning/driving/oct_gen/
adc/*.m     →  projects/adc/apps/planning/…/oct_gen/
common/*.m  →  被 afc/adc 引用的白名单助手（如 gf_clamp）
```

**原则：** 一函数一关注点；`.m` 与 C/`oct_gen`/`ops` **算法一一对应**。  
最终二进制：`gf_planning_driving` = 薄壳 + `oct_gen` + `gf_octave_planning`。

详见：

- [`tools/gf-octavecoder/README.md`](../tools/gf-octavecoder/README.md)
- [`tools/gf-octavecoder/PLAN.md`](../tools/gf-octavecoder/PLAN.md) — 分阶段与防回归
