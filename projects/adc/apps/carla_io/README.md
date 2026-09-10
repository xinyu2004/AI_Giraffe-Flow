# gf_carla_io（板端 / SIL）

Giraffe 侧独立程序：TCP cosim ↔ **`giraffe_client`**；写/读本地 GfChannel。

- **进：** `vehicle_state` / `fake_perc` / 相机 NV12  
- **出：** `vehicle_cmd`（gateway → 上位机拧车）  
- **无** Python、**无** libcarla  
- `GF_FRAME_SOURCE=carla` 时由 `gf_frame_ingest` exec  

监听：`GF_COSIM_PORT`（默认 7600）。协议见 `gf_channel/cosim_protocol.h`。

上位机：`carla_scenarios/giraffe_client/`。总览：[gateway_boundary.md](../../../../docs/zh/sku/afc/gateway_boundary.md)。
