# afc runtime 体积说明

实测（本机 `build-sil`，目录整理时）：

| 路径 | 约 | 性质 |
|------|-----|------|
| `build-sil/` 整树 | ~420M | **编译产物**（iceoryx/posh/lib…），不是上板包 |
| 真正 stage：`bin+lib+share+etc` | **~5M 量级** | 上板/自包含运行树 |

## 已做精简

1. **obs 仅在需要时写入**：`gf_obs_dir` → `build-sil/observability`（GMT GUI **Record** 落盘，默认 `gmt_record.jsonl`；**无** run_sil 自动 tee）。
2. **日志走 console + DLT**：产品路径 **不传 `--log-dir`**；子进程继承 TTY。`--log-dir` / `GF_EM_LOG_DIR` 仅可选调试。
3. **stage 去掉 USS**（本 SKU 无 USS）。
4. **`GF_STAGE_PY=0`**：HIL/板端可不 stage Python share。
5. **`GF_STAGE_DEBUG_BRIDGE=0`**：可不 stage tap/inject。

清理历史膨胀（一次性，若曾跑旧版 SIL）：

```bash
rm -rf projects/afc/build-sil/runtime/observability \
       projects/afc/build-sil/runtime/logs \
       projects/afc/build-sil/logs
# 或 GF_FORCE_COMPILE=1 bash projects/afc/scripts/run_sil.sh（wipe runtime 后再 sync）
```

`build-sil` 四百兆级属正常（含 iceoryx 构建）；勿与 **runtime 载荷**混淆。
