# adc — scripts

本 SKU **尚无** `compile_sil` / `run_sil` / `giraffe_launch` 产品壳（与 `afc` 不同）。

当前仅有桌面/MCU 验收 smoke：

```bash
bash projects/adc/scripts/verify/smoke_mcu_desktop.sh
```

若要对齐 afc 合同（mtime compose、按需 cmake configure、`GMT_depend_launch`），需新增 `scripts/{_common,compile_sil,run_sil,…}.sh`；在此之前请用仓根 `cmake -B build` 或 `projects/afc` 路径做联调。

验收细节见 [`verify/`](verify/)。
