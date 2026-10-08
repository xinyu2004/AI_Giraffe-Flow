# EM App 间 DAQ（计划稿 · 后置）

> **状态：** backlog。**现在没有这层能力。** SIL 旁路 `gf_iox_obs_tap` / Foxglove / GMT **不是**产品 DAQ。  
> **何时细化：** 泊车做完后再开。ID：[BL-APP-DAQ](AP_LITE_BACKLOG.md)。

## 原意（先锁，细则后补）

EM 拉起的 SOA App 之间要有 **DAQ**：能采到 App 间真正在发的数据，最好挂在通信/运行时底层（环缓、可采样、可关），而不是再开一个订户进程当「已交付」。

不是：

- `collector`（事件 / DEM-lite / DTC）
- GMT / Foxglove 自己当采集核（它们是看见/录盘的上位机）
- 把现有 `live_tap` 旁路改名成 DAQ

## 现有对照

| 层 | 现在 | 和本条的关系 |
|----|------|----------------|
| tap 进程 | 白名单再订一份 semantic → NDJSON | debug-path；`production-release` 不编 |
| collector | `ReportEvent` 环缓 | 诊断，不是信号 DAQ |
| `middleware/trace` | 空骨架 | 计划挂底层的落点，**未实现** |

## 回来时要定（先不写死）

- 采在 com 边还是独立 Trace Agent；谁随 EM 拉起、谁可裁
- 板端默认采样、禁止全量 payload（与 DESIGN / WORKFLOW 一致）
- 和 tap / GMT / VCD 的导出关系：上位机继续吃导出，不把 GUI 上车
- production profile 如何关或只留采样

本文件在泊车收口前 **不扩写、不接线**。
