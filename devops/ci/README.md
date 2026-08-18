# devops/ci

编排层：本地门禁与未来云 CI 都从这里进，避免在 workflow 里散落调底层脚本。

**政策摘要（2026-08）：** 发版最谨慎；PR 按路径加跑工具链 SIL；DoIP 仅 nightly/发版；不冒烟刷写/SWU；cyclone/iox nightly 保活，待真使能 DDS/SOME/IP 再升 PR。

## 脚本入口

| 脚本 | 层 | 用途 |
|------|----|------|
| [scripts/smoke.sh](scripts/smoke.sh) | **L0** | PR 主体：bootstrap → pytest → compose/lint → architect → cmake/ctest → `smoke_sil` → optional aarch64 |
| [scripts/smoke_toolchain.sh](scripts/smoke_toolchain.sh) | **L0b / L3** | observability → inject → gmt_vcd；`GF_CI_INJECT_B2=1` 时加 inject_b2 |
| [scripts/smoke_nightly.sh](scripts/smoke_nightly.sh) | **L2** | L0 + cyclone + iox + **DoIP** + FuSa SIL |
| [scripts/smoke_release.sh](scripts/smoke_release.sh) | **L3** | L0 + 全量工具链（含 inject_b2）+ L1 + DoIP + T4 + **`GF_FUSA_PACK_RELEASE=1` 证据包** |

```bash
bash devops/ci/scripts/smoke.sh
GF_SKIP_COMPILE=1 bash devops/ci/scripts/smoke_toolchain.sh
bash devops/ci/scripts/smoke_nightly.sh
bash devops/ci/scripts/smoke_release.sh
```

## 分层总览

| 层 | 何时跑 | 说明 |
|----|--------|------|
| **L0** | 每次 PR / push | 主体门禁；中间件/cmake 通用改动到此为止 |
| **L0b** | 路径命中（见下） | **强制**跑 `smoke_toolchain.sh`；失败与 L0 同等挡合入 |
| **L1** | nightly 必跑；PR 默认不挡 | `smoke_bd_cyclone.sh` · `run_iox_demo.sh`（DDS/SOME/IP 就绪） |
| **L2** | schedule nightly | DoIP 通路 + FuSa SIL；**不**刷写 |
| **L3** | tag / 发版 checklist | 最谨慎：工具链 SIL **必跑** + L1 + DoIP + T4 + **FuSa evidence pack** |

## PR 路径触发（L0b）

| 改动路径（任一条命中） | 额外跑 | 挡合入 |
|------------------------|--------|:------:|
| `tools/gmt/**` | `smoke_toolchain.sh`（observability · inject · gmt_vcd） | 是 |
| `tools/gf-config/**` | 同上 **强制** `smoke_toolchain.sh` | 是 |
| `tools/gf-codegen/**` · `schemas/**` | 同上 **强制** `smoke_toolchain.sh`（与 config 同套，生成契约影响观测主链） | 是 |
| `middleware/diag/**` · `middleware/ucm/**` | **不**强制 DoIP → nightly | — |
| Cyclone / iceoryx / bindings 相关 | **不**强制 L1 → nightly | — |

主体 PR（未命中上表）只跑 **L0**。

建议顺序：先 L0，再 `GF_SKIP_COMPILE=1` 跑 toolchain（复用 `build-sil`）。若尚无 `projects/.../build-sil`，toolchain 脚本内各 smoke 会自行 compile（除非设了 skip 且缺产物则失败——发版脚本会先保证 compile）。

## 发版门禁（L3）

入口：`bash devops/ci/scripts/smoke_release.sh`

必过：

1. L0  
2. 工具链 SIL：observability · inject · **inject_b2** · gmt_vcd  
3. cyclone · iox  
4. `smoke_doip_ota.sh`（仅通路，无刷写）  
5. `GF_FUSA_T4=1`  
6. **FuSa evidence**：`GF_FUSA_PACK_RELEASE=1` → `projects/.../generate_fusa_artifacts.sh`  
   - 落盘 `fusa/packs/oem_a_afc_with_uss/`（含 `release/RELEASE_GATE.md` · `MANIFEST.md` · `SHA256SUMS`）  
   - **硬校验**必有：SOR、lineage、`session.mcap`、`cases_latest.log`、`session_stub.vcd`  

**不做**：SWU 打包、真刷写冒烟。默认不把 `fusa/packs/` 提交进仓。

## 平台旁路（L1）与后续 DDS / SOME/IP

今日 iceoryx 主链；Cyclone / iox demo nightly 保活。真使能 DDS / SOME/IP 后，将 L1 升为 PR 必过或并入 L0，脚本名可不变。

## 云 CI

样例：[workflows/ci.yml.example](workflows/ci.yml.example)（复制为 `.github/workflows/ci.yml` 后启用）。已含路径 filter：GMT / gf-config / codegen / schemas → toolchain。
