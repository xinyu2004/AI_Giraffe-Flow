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
| BL-MEM-BOUND | **全模块有界内存**（环缓/配额；禁无界 `vector` 增长） | deferred | 平台硬化波 | log/DLT 子集已有界；collector/com 等仍待审 |
| BL-SQLITE | SQLite per | deferred | 仅强查询需求 | 默认双槽文件 KV |
| BL-ISOTP-AP | ISO-TP on AP | deferred | 仅「AP 直挂 CAN」SKU | 默认战略不做；CAN 在 MCU |
| BL-CLASSIC | Classic DEM/DCM | wontfix | — | 用 collector DEM-lite + diag DCM-lite |
| BL-UDS-11 | 0x11 真复位 | deferred | 板级策略 | SIL：正响应 + 事件 |
| BL-UDS-19FULL | 全量 0x19 子功能 | deferred | 按 OEM 增量 | 本轮最小集 + 冻结帧读 |
| BL-GMT-COLL-LIVE | GMT Collector 真·live（ws 推送，非轮询） | deferred | 观测波 | 现：文件 + UDS RID F201 |
| BL-COLL-FILTER | runtime 按 collector.yaml `sources` 过滤 ReportEvent | deferred | 平台波 | 配置意图已有；运行时尚未滤 |

## 本轮已纳入（对照，非后置）

- `gf_ara::per` 双槽文件 KV
- DEM-lite：防抖 / FDC / pending+confirmed / occurrence / operation-cycle 老化 / 0x19·14·85
- Freeze frame（门禁 G1 之后）
- UCM：yaml 加载、Present、版本→per、SoftwareCluster
- log：彩色、按模块设 level、sinks（console/file/dlt）；上位机走 DLT
- `gf_ara::tsync` gPTP lite（linuxptp 后端）
