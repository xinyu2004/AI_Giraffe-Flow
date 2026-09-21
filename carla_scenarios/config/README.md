## Host camera + spectator mounts

```text
config/<product>/camera_contract.json     # 产品相机（gf-config / compose）
config/spectator/windshield.mount.json    # env ChaseCam=1
config/spectator/bev_afc.mount.json       # env ChaseCam=2（对齐 paint afc）
config/spectator/bev_adc.mount.json       # env ChaseCam=3（对齐 paint adc）
config/spectator/overhead.mount.json      # env ChaseCam=4
```

Paint BEV 观测（**不在本树**）：

```text
tools/gmt_board/iox_obs_foxglove/config/afc/bev.mount.json
tools/gmt_board/iox_obs_foxglove/config/adc/bev.mount.json
```

| env | 作用 |
|-----|------|
| `GF_CAMERA_CONTRACT=afc` | → `config/afc/camera_contract.json` |
| `GF_CAMERA_CONTRACT=config/afc/camera_contract.json` | 显式路径 |
| `ChaseCam=1\|2\|3\|4` | 旁观：windshield / bev_afc / bev_adc / overhead |
| `GF_MOUNTS_JSON=…/bev.mount.json` | paint BEV 观测覆盖 |
| `GF_BEV_SKU=afc\|adc` | 选 paint 默认 `…/config/<sku>/bev.mount.json` |

**产品光学真源**：`projects/<product>/req.yaml` → Verify/compose → `camera_contract` +（目标）冻结核 `fs_envelope_cal` 常量（7/35/fov）。  
**BEV 旁观**：paint 只读自己的 `bev.mount`；CARLA 只读 `config/spectator/`；不算 FS。

轻量只传部分相机：`GF_COSIM_CAMERAS=front`
