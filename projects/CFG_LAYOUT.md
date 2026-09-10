# SKU 作者树布局（`cfg/`）

> **一刀切（2026-09）：** 入口 `giraffe.yaml`；作者源一律在 `cfg/`。旧名 `project.yaml` / 根 `req.yaml` / `integration/wiring.yaml` / `platform/*` 已废除。

## 目录

```text
projects/<sku>/
  giraffe.yaml           # 唯一入口索引（无业务细节）
  cfg/
    req.yaml             # SKU / SOR 交付分解（文件名保留 req）
    wiring.yaml          # 集成连线 + canvas
    gf_ara_cfg/          # 中间件运行时作者树（gf-config 页 2）
      exec.yaml
      em_launch.yaml
      phm.yaml
      …
  oem/  reports/  generated/
```

## 三面口诀

| 文件 | 角色 |
|------|------|
| `cfg/req.yaml` | 要什么、裁多深、验什么 |
| `cfg/wiring.yaml` | 谁跟谁说话 |
| `cfg/gf_ara_cfg/*` | EM/SM/PHM/log… 怎么跑 → Verify 冻 hpp |

**`gf_ara_cfg` ≠ 全部 gf-config 输出**；只是中间件运行时那一层。

## 工具

```bash
gf-config projects/afc/giraffe.yaml
# 或：文件 → 新建 Giraffe 工程…（scaffold 最小完备树）
python -m gf_codegen.compose --project projects/afc/giraffe.yaml
```

SOR 合成产物键：**`gf_ara_cfg_manifest`**（由 `cfg/gf_ara_cfg` merge）；作者 YAML 键是 `gf_ara_cfg:`。

## 运行期命名（与作者树对齐，一刀切）

| 角色 | 名字 |
|------|------|
| 作者目录 | `cfg/gf_ara_cfg/` |
| SOR 合并表 | `gf_ara_cfg_manifest` |
| 环境变量 | `GF_ARA_CFG_DIR`（产品路径默认 **不设** = hpp-only） |
| EM CLI | `--ara-cfg DIR` |

```bash
# smoke 显式作者树
export GF_ARA_CFG_DIR=projects/afc/cfg/gf_ara_cfg
gf_em_daemon --ara-cfg "$GF_ARA_CFG_DIR" --launch "$GF_ARA_CFG_DIR/em_launch.yaml" --build-dir …
```
