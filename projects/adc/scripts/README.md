# adc — scripts

产品路径：`compile_sil.sh` → `run_sil.sh`（见上级 [README.md](../README.md)）。

常用：

```bash
bash projects/adc/scripts/compile_sil.sh
GF_FRAME_SOURCE=carla bash projects/adc/scripts/run_sil.sh
bash projects/adc/scripts/verify/smoke_sil_drive_park_fg.sh
```

MCU IPC 烟测在 `middleware/bindings/cross_domain_ipc/testcases/`，不在本目录。
