# scripts/

Host-side / repo-wide helpers. **SKU 产品主路径**在各 `projects/.../scripts/` 仅四入口：`compile_sil` / `compile_hil` / `run_sil` / `run_hil`。

| Script | Purpose |
|--------|---------|
| [bootstrap_deps.sh](bootstrap_deps.sh) | toolchains；attr/acl → deps-prefix；iceoryx / cyclonedds |
| [run_iox_demo.sh](run_iox_demo.sh) | 双进程 RouDi demo（验证用） |
| [verify/](verify/) | **模块/功能 smoke**（非产品路径） |
| [cross_link_smoke.sh](cross_link_smoke.sh) | optional aarch64 link |
| [run_ab_loop.sh](run_ab_loop.sh) | Deprecated → `verify/.../smoke_sil.sh` |
| [smoke_bd_stub.sh](smoke_bd_stub.sh) | DDS/SOMEIP stub smoke |
| [smoke_bd_cyclone.sh](smoke_bd_cyclone.sh) | CycloneDDS 真收发 |
| [collect_p2_evidence.sh](collect_p2_evidence.sh) | P2-G 证据包 |

```bash
# 产品主路径
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# 验证
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh
```

### Policy (board / cross)

`runtime_board` deps 见 [deps/](../deps/) 与 [middleware/third_party/](../middleware/third_party/)。  
Pins: [deps/versions.lock.md](../deps/versions.lock.md)
