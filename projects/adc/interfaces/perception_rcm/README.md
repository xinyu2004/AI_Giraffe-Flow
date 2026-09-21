# perception_rcm — Rear Camera Module

FCM **小集**：变道后向态势。SIL 金源 = CARLA `gf.channel.rcm_truth`（非后视像素推理）。

| | |
|--|--|
| 进程 | `perception.rcm` → `gf_perception_rcm` |
| 相机 | `gf.channel.rear`（frame_id / 健康；不算检测） |
| 真值 | `gf.channel.rcm_truth` ← giraffe_client MSG 15 |
| Provide | `Perception_Rear_Out_St`（线+目标+速度；无 TSR） |
| 缺包 | **沉默**（不发）；不发明 |
| 消费 | `planning.driving_plus` 缓存；变道逻辑后挂 |

≠ surround（fl/fr/rl/rr + Near/World）。前视仍只走 FCM←`fake_perc`。
