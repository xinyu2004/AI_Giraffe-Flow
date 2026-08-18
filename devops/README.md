# devops/

持续集成 / 持续交付编排（主机门禁与发版约定）。**不**把业务运行时放在这里。

| 目录 | 角色 |
|------|------|
| [ci/](ci/) | 门禁分层：L0 `smoke.sh` · L0b `smoke_toolchain.sh` · L2 `smoke_nightly.sh` · L3 `smoke_release.sh`；云 CI 样例 |
| [cd/](cd/) | 交付约定：SIL/HIL/板端制品与发布（占位，无云密钥） |

政策与路径触发详见 [ci/README.md](ci/README.md)。

```bash
# L0 日常
bash devops/ci/scripts/smoke.sh

# L0b 工具链（GMT / gf-config / codegen / schemas 改动时强制）
GF_SKIP_COMPILE=1 bash devops/ci/scripts/smoke_toolchain.sh

# L2 nightly · L3 发版
bash devops/ci/scripts/smoke_nightly.sh
bash devops/ci/scripts/smoke_release.sh

# FuSa（仍在 fusa/，不经 devops 转发）
bash fusa/scripts/run_cases.sh
```

Board jobs must not pull host-only UI/ROS deps — see [dep-manifest/README.md](../dep-manifest/README.md).
