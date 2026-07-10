# 部署边界

车型交付与部署裁剪统一在 **`req.yaml`**（不再单独 `deploy/profile.yaml`）。

- 示例：[`projects/oem_a/afc_with_uss/req.yaml`](../../../projects/oem_a/afc_with_uss/req.yaml)
  - 契约：`topology` / `bindings` / `runtime_modules` / `acceptance`
  - 裁剪：`observability` / `apps`（参考进程清单）
- 主机 vs 交叉、在哪跑：项目 `scripts/`（`compile_sil` / `compile_hil`）
- 改款：复制整个 `projects/<oem>/<product>/`，在副本内改 `req.yaml` 等

见 [DESIGN.md §7](DESIGN.md) · [projects/README.md](../../../projects/README.md)
