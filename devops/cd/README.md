# devops/cd

持续交付约定（占位）。**不接**真实云发布密钥；真板部署属 P3z。

| 内容 | 说明 |
|------|------|
| 制品 | SIL 二进制树、`fusa/packs/`、可选板端镜像清单 |
| 脚本 | [scripts/](scripts/) — 打包 / 发布占位 |
| Workflow | [workflows/cd.yml.example](workflows/cd.yml.example) |

```bash
# 占位：打印约定路径（实现前仅 echo）
bash devops/cd/scripts/package_sil.sh
```

与 [ci/](../ci/) 分工：CI 验证「能过」；CD 约定「如何打包交付」。
