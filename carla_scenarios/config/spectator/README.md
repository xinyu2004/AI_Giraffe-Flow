# Spectator mounts (CARLA pygame / lab view)

`carla.env` 编号 **1/2/3/4** ↔ 本目录文件名：

| env `ChaseCam` | 文件 | 含义 |
|----------------|------|------|
| **1** | `windshield.mount.json` | 风挡 |
| **2** | `bev_afc.mount.json` | AFC BEV 旁观 |
| **3** | `bev_adc.mount.json` | ADC BEV 旁观 |
| **4** | `overhead.mount.json` | 俯视 |

Paint 用的投影配置在  
`tools/gmt_board/iox_obs_foxglove/config/{afc,adc}/bev.mount.json`  
（与 #2 / #3 数值对齐，**不属于**本目录）。

产品光学：`config/<product>/camera_contract.json`（gf-config）。
