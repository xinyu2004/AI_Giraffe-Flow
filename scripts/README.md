# scripts/

Host-side / repo-wide helpers. **SKU 产品主路径**在各 `projects/.../scripts/`。

**模板（拷贝后分叉）**：[common/](../common/README.md)  
**板端入口**：[common/deploy/](../common/deploy/) → systemd / init.d → `gf_em_daemon`  
`giraffe_launch` 仅主机调试。

| Script | Purpose |
|--------|---------|
| [bootstrap_deps.sh](bootstrap_deps.sh) | → `dep-manifest/bootstrap.sh`（toolchains；attr/acl → deps-prefix） |
| [run_iox_demo.sh](run_iox_demo.sh) | 双进程 RouDi demo（中间件冒烟） |
| [smoke_bd_cyclone.sh](smoke_bd_cyclone.sh) | CycloneDDS 真收发旁路冒烟 |
| [cross_link_smoke.sh](cross_link_smoke.sh) | optional aarch64 link |
| FuSa | [fusa/scripts/run_cases.sh](../fusa/scripts/run_cases.sh)；SKU pack → `projects/.../generate_fusa_artifacts.sh` |

日常质量门禁见 [devops/ci/](../devops/ci/README.md)（`smoke.sh` / `smoke_toolchain.sh` / `smoke_nightly.sh` / `smoke_release.sh`）。  
SKU 验收 smoke 见 `projects/<oem>/<sku>/scripts/verify/`；平台编排进 devops/ci，SKU 脚本仍为真源。

```bash
bash scripts/bootstrap_deps.sh
bash common/bootstrap_sku_scripts.sh afc
# gf-config: Save → Verify →（需要时）Generate
bash projects/afc/scripts/compile_sil.sh
bash projects/afc/scripts/run_sil.sh
# 板端：拷 runtime/ + 安装 common/deploy/systemd/giraffe-em.service.example
```
