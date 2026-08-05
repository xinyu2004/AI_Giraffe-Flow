# Giraffe_Flow（架构总览图）

**真相源：** `scripts/render_gif.py`  
**产物（单份，避免残留）：**

| 文件 | 说明 |
|------|------|
| `Giraffe_Flow.gif` / `.svg` | 中文（README 主引用） |
| `Giraffe_Flow.en.gif` / `.en.svg` | 英文 |
| `assets/carla.png` / `foxglove.png` | 可替换图标 / Studio 截图 |

## 再生

```bash
# 需 Pillow + 本机 CJK 字体（Noto / DejaVu）
python3 result_pic/Giraffe_Flow/scripts/render_gif.py
```

## 布局要点

- 竖向：`gf-config` → **GIRAFFE 模块** → `GMT`
- 板内：SoC → **FuSa** → **SOA apps**（FuSa 在上）
- 左：CARLA → 板（漏斗箭头：左粗右细 = 视频/大数据入）
- 右：板 → Foxglove（比 GMT tap 线粗，比 CARLA 漏斗克制）
