# Host camera contracts (exported by compose / gf-config Verify)

```text
config/<product>/camera_contract.json
```

| env | 作用 |
|-----|------|
| `GF_CAMERA_CONTRACT=afc` | → `config/afc/camera_contract.json` |
| `GF_CAMERA_CONTRACT=config/afc/camera_contract.json` | 显式路径 |

**真源**：`projects/<product>/req.yaml` → Verify/compose → 写  
`generated/camera_contract.json` 与本目录。  
上位机 **不要** `GF_PROJECT_DIR`；路数由 product 配置决定。

（全局把文档里的 sku 改成 product / `GF_PRODUCT` 后置。）

轻量只传部分相机：`GF_COSIM_CAMERAS=front`
