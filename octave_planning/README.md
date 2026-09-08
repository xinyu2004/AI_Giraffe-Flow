# octave_planning/ — 仅 `.m` 金源

```text
afc/*.m     →  projects/afc/apps/planning/driving/oct_gen/
adc/*.m     →  projects/adc/apps/planning/…/oct_gen/
common/*.m  →  被 afc/adc 引用的白名单助手（`gf_clamp` / `gf_plan_cal` / `gf_lane_usable` / horizon / v_at_s / lon_exec / reg_stop / …）
换车 ≈ 换 `gf_lon_exec`（踏板/起步）；换标定 ≈ 换 `gf_plan_cal`；灯/牌停车线 ≈ `gf_plan_reg_stop` + `gf_plan_v_reg`（不进 occupy）。
```

**原则：** 一函数一关注点；`.m` 是金源。**先改 `.m`，Host 认效果，再 generate C**——未认可前不要为 1:1 去改 hpp/`oct_gen`。  
Host 入口：`afc/m_plan_tick.m`（一拍一次；`traj_n × obj_n_max`）。  
最终二进制：`gf_planning_driving` = 薄壳 + `oct_gen` + `gf_octave_planning`（generate 之后）。

规划 v4 合同（视野内路径+分段速度，类 A*，非本拍分档）：[`docs/zh/driving/planning_lon_v4.md`](../docs/zh/driving/planning_lon_v4.md)。

**ME 语义（SIL）：** 停车约束只吃 `Relevancy=0` 的 196/164；绿灯 SIL=`198`（规划忽略）；Live 用 Trajectory `D_see_m` / `s_stop_m` / `cipv_*` / `v_sign_*`，禁止用 `Sign_Name[0]` 验收。见 `.cursor/rules/me-semantic-alignment.mdc`。

详见：

- [`tools/gf-octavecoder/README.md`](../tools/gf-octavecoder/README.md)
- [`tools/gf-octavecoder/PLAN.md`](../tools/gf-octavecoder/PLAN.md) — 分阶段与防回归
