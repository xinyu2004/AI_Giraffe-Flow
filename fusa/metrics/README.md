# FuSa metrics — 测量与隔离索引

本目录给 Safety Case / 架构评审用：**行为对不对**见 isolation；**大概多快**见 latency。  
都不是量产 ECU 合格判据；GMT 仍属 debug-path。

| 文档 | 回答什么 | 不回答什么 |
|------|----------|------------|
| [isolation.md](isolation.md) | 故障注入后能否按期望隔离 / 恢复（PASS/FAIL + SG） | 具体毫秒预算是否达标 |
| [latency.md](latency.md) | 参考延时快照（检测 / soft 恢复 / EM relaunch / 采样周期…） | 是否已获证；真 hop e2e（尚未打点） |

## 怎么跑

```bash
# 行为矩阵（含 SIL-03 / SIL-EM-02）—— 不解析延时数字
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh

# 延时快照 → fusa/runs/measure_summary_*.json（gitignore）
bash fusa/scripts/measure_latency.sh
```

`run_cases` 与 `measure_latency` **互不调用**；数字填进 `latency.md` 后，isolation 表可引用最近 PASS。

追溯：[../safety-case/](../safety-case/) · 政策：[../POLICY.md](../POLICY.md)
