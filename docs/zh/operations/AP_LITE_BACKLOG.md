# AUTOSAR AP lite — 后置登记册

> 产品定位：可上板的 **AUTOSAR Adaptive Platform lite**（`gf_ara::*`）。  
> 本文件登记**本轮不做**、防止遗忘的条目。ID 稳定；只改状态，不删行。  
> 关联：[ROADMAP.md](ROADMAP.md) · [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)

| ID | 项 | 状态 | 目标波次 | 备注 |
|----|-----|------|----------|------|
| BL-COM-METHOD | com Method/Field 完整 | deferred | SOA 通信波 / 与 vsomeip 同波 | Event 主链已有 |
| BL-SOMEIP | vsomeip 真栈 | deferred | 同上 | binding 现 stub |
| BL-CRYPTO | crypto / 证书 | deferred | 量产安全门禁 | |
| BL-IAM | iam | deferred | 同上 | |
| BL-IDSM | idsm | deferred | 同上 | |
| BL-NM | nm | deferred | 同上 | |
| BL-FW | firewall / shwa | deferred | 同上 | |
| BL-UCM-SIGN | UCM 非对称验签 | deferred | 与 crypto 同波 | Verify 钩子预留 magic/manifest |
| BL-RAUC | RAUC 真刷 A/B | deferred | P3z 真板 | 本轮留 adapter 接口 |
| BL-DLT | DLT（libdlt + daemon + GMT 客户端） | **done** | 见 [DLT_PLAN.md](DLT_PLAN.md) | `gmt_export` 已清；真板 = rootfs 手验 |
| BL-MEM-BOUND | **全模块有界内存**（环缓/配额；禁无界 `vector` 增长） | **done** | 平台硬化波 | `bounds.yaml` + gf-config「有界内存」+ Verify `mem_budget`（公式见 `mem_budget.py` FORMULAS）；运行时强制 log/collector/com/per/DoIP/DID |
| BL-MEM-ROUDI | **RouDi / iceoryx SHM 有界**（mgmt IOX_* + mempool TOML） | **done** | 平台硬化波 | `bounds.iceoryx` → `iox_mgmt.cmake` + `iox_roudi.toml`；`req.bindings` 含 iceoryx 才起 RouDi；改 mgmt 需 rebuild iceoryx |
| BL-SQLITE | SQLite per | deferred | 仅强查询需求 | 默认双槽文件 KV |
| BL-ISOTP-AP | ISO-TP on AP | deferred | 仅「AP 直挂 CAN」SKU | 默认战略不做；CAN 在 MCU |
| BL-CLASSIC | Classic DEM/DCM | wontfix | — | 用 collector DEM-lite + diag DCM-lite |
| BL-UDS-11 | 0x11 真复位 | deferred | 板级策略 | SIL：正响应 + 事件 |
| BL-UDS-19FULL | 全量 0x19 子功能 | deferred | 按 OEM 增量 | 本轮最小集 + 冻结帧读 |
| BL-GMT-COLL-LIVE | GMT Collector 真·live（ws 推送，非轮询） | deferred | 观测波 | 现：文件 + UDS RID F201 |
| BL-COLL-FILTER | runtime 按 collector.yaml `sources` 过滤 ReportEvent | **done** | 平台波 | 非空 `sources` 白名单；空=不过滤；现已冻进 `collector_config.hpp` |
| BL-CFG-YAML-FALLBACK | 去掉 bringup/DoIP「无 hpp 时 `GF_PLATFORM_DIR`→yaml」回落 | deferred | 配置硬化收口 | 今日：有对应 `GF_HAS_*` 头则只读 hpp；无头且显式设了 `GF_PLATFORM_DIR` 才读作者 yaml（smoke）。目标：SKU 构建强制头齐全，删 yaml 回落路径 |
| BL-IOX-SHM-USED | iceoryx SHM 度量改为**实际使用**而非**分配/预留** | deferred | 平台硬化 / 观测 | 今日 `mem_budget` / `iox_shm_report` 多为 RouDi reserve / mempool **allocated** 上界；需区分 used vs allocated（payload 占用、mgmt 实测）并进 Verify/UI |
| BL-BOARD-NO-PY | **板端 runtime 零 Python**（含 frame_ingest） | deferred | P3z 真板 / 载荷收口 | **政策：**凡会随 `runtime/` / GMT 依赖上板的组件，**不得**依赖 Python 解释器或 `share/**/*.py`。`gf_frame_ingest` 板端路径 = C++ only（Create GfChannel + ISP/V4L 等适配，**禁止** `execlp(python…)`）。`carla_bridge.py` / replay / colorbar 模块 **仅宿主机 SIL**；板端 stage **不得**打进 Python 模块。资源：板端环境复杂且紧，Python 运行时与依赖一律不上板 |
| BL-STAGE-PY-MTIME | stage 对 SIL 主机侧 `tools/carla_bridge/*.py` 做 mtime 增量拷贝 | deferred | SIL 工具链卫生 | 仅影响**宿主机** SIL；与 BL-BOARD-NO-PY 正交。今日改 py 后 `compile_sil` 常 skip stage → 仍跑旧拷贝 |
| BL-GMT-FOX-PY | Python Foxglove 收口（JSONL 回放 / MCAP 辅助 / Host `octave_bridge/foxglove_ws.py`） | deferred | 观测收口 | SIL 直播已是 C `gf_foxglove_ws`；已删 `--stdin`。目标：C 读 JSONL 或 Host 也走 C 后再删 `bridge_foxglove.py` |

## 本轮已纳入（对照，非后置）

- `gf_ara::per` 双槽文件 KV
- DEM-lite：防抖 / FDC / pending+confirmed / occurrence / operation-cycle 老化 / 0x19·14·85
- Freeze frame（门禁 G1 之后）
- UCM：yaml 加载、Present、版本→per、SoftwareCluster
- log：彩色、按模块设 level、sinks（console/file/dlt）；上位机走 DLT
- `gf_ara::tsync` gPTP lite（linuxptp 后端）
