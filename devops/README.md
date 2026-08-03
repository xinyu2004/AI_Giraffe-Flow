# devops/

持续集成 / 持续交付编排（主机门禁与发版约定）。**不**把业务运行时放在这里。

| 目录 | 角色 |
|------|------|
| [ci/](ci/) | 日常 / PR 门禁：`smoke.sh`、云 CI 样例 |
| [cd/](cd/) | 交付约定：SIL/HIL/板端制品与发布（占位，无云密钥） |

```bash
# 日常门禁
bash devops/ci/scripts/smoke.sh

# FuSa（仍在 fusa/，不经 devops 转发）
bash fusa/scripts/run_cases.sh
```

Board jobs must not pull host-only UI/ROS deps — see [dep-manifest/README.md](../dep-manifest/README.md).
