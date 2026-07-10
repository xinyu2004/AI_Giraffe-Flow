# gf-codegen 详细实施说明（P0）

> 总计划：[P0_PLAN.md](../../docs/zh/operations/P0_PLAN.md)  
> 验收项目：[projects/oem_a/afc_with_uss/](../../projects/oem_a/afc_with_uss/)  
> 状态：**代码已落地 2026-07-10** — A1–A5 MVP 已完成（`afc_with_uss` compose / lint / suggest / generate）。

**目标一句话：** 在主机用 Python 做出 `gf-codegen`，使下面命令成功，并为 `afc_with_uss` 写出 SOR + lineage：

```bash
pip install -e tools/codegen
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
```

---

## 1. 范围与非目标

### 1.1 P0 必须做

| 命令 | 必须 |
|------|------|
| `gf-codegen --help` / `--version` | 可安装入口 |
| `gf-codegen lint PATH` | schema 必填 + 基础结构检查 |
| `gf-codegen compose --project PATH` | 读四类输入 → `gf.sor.json` + lineage |
| `gf-codegen suggest wiring --project PATH` | 打印建议 YAML（可后于 compose 1～2 天） |
| `gf-codegen generate PATH --out DIR` | **最小 types 头**（尚无 Proxy/Skeleton） |

### 1.2 P0 明确不做

- GMT GUI、拖拽写回  
- libclang / 完整 C++ AST  
- ARXML、SOME/IP/DDS 配置生成  
- 把工具打进板端镜像  
- 一次打通 `adc_full`（可作回归加分项，非第一刀）

---

## 2. 工程骨架（第 0 天）

### 2.1 目录

```text
tools/codegen/
  pyproject.toml
  README.md
  IMPLEMENTATION.md          # 本文
  src/gf_codegen/
    __init__.py              # __version__ = "0.1.0"
    cli.py                   # 入口
    paths.py                 # 相对仓库根 / project 目录解析
    models.py                # 内部 dataclass（可选）
    schema_load.py
    lint_cmd.py
    compose/
      __init__.py
      pipeline.py            # compose 主编排
      load_project.py
      import_oem.py
      parse_hpp.py
      apply_wiring.py
      merge_req.py
      lineage.py
      write_sor.py
    suggest_cmd.py           # A4
    generate_cmd.py          # A5
  tests/
    conftest.py              # repo_root fixture
    test_lint_golden.py
    test_parse_hpp.py
    test_compose_afc_with_uss.py
```

### 2.2 `pyproject.toml`（建议）

```toml
[project]
name = "gf-codegen"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "pyyaml>=6.0",
  "cantools>=39.0",
  "jsonschema>=4.0",
]

[project.scripts]
gf-codegen = "gf_codegen.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

安装：

```bash
cd /path/to/AI_Giraffe-Flow
python3 -m venv .venv && source .venv/bin/activate
pip install -e "tools/codegen[dev]"   # 或 pip install -e tools/codegen
pytest tools/codegen/tests -q
```

### 2.3 CLI 形状（`cli.py`）

用 `argparse` 即可（少依赖）：

```text
gf-codegen lint <sor.json> [--schema schemas/gf.sor.schema.json]
gf-codegen compose --project <project.yaml> [--out PATH] [--repo-root PATH]
gf-codegen suggest wiring --project <project.yaml> [--write]
gf-codegen generate <sor.json> --out <dir>
```

`--repo-root` 默认：从 `project.yaml` 向上找含 `schemas/` 与 `projects/` 的目录；测试里可显式传入。

---

## 3. 切片 A1 → A5（按天可执行）

### A1 — 空壳可运行（0.5 天）

1. 建 `pyproject.toml` + `src/gf_codegen/cli.py`  
2. `main()` 打印 help / version  
3. 验收：`gf-codegen --help` 退出 0  

### A2 — `lint`（1 天）

**算法：**

1. `json.load` SOR  
2. 用 `jsonschema` 校验 `schemas/gf.sor.schema.json`（当前 schema 较松，主要抓缺 `schema_version/types/services/deployments`）  
3. **额外硬规则**（schema 未写死的也要查）：  
   - `services[].id` 唯一  
   - `deployments[].process` 唯一  
   - 若存在 `dataflows`，`from`/`to`/`service` 字段齐全  

**验收：**

```bash
gf-codegen lint projects/oem_b/adc_full/golden/gf.sor.json
gf-codegen lint schemas/examples/desktop_ap_only.sor.json
# 故意删掉 deployments 应非 0 退出
```

单测：`test_lint_golden.py`。

### A3 — `compose`（核心，3～5 天）

见 **§4**。验收见 **§6**。

### A4 — `suggest`（1～2 天，可紧随 A3）

输入：project → dbc 消息名、hpp struct 名、现有 wiring。  
输出：stdout YAML 片段，例如：

```yaml
# suggested bindings (review before merge)
- module: sensing.uss
  outputs:
    - { service: semantic.UssZones, type: UssZones }
```

启发式（P0 够用）：

- struct 名 `UssZones` → 建议 `services.semantic.UssZones`  
- struct 名 `EgoMotion` → `services.semantic.EgoMotion`  
- DBC 消息 `P_VEHICLE_INFO` → gateway provide EgoMotion  
- 唯一 provider 的 semantic → 预链到所有 require 它的 process  

默认**不写盘**；`--write` 才改 wiring（P0 可先不做 `--write`）。

### A5 — `generate`（2～3 天，可并行于 runtime）

输入：SOR。  
输出目录示例：

```text
generated/
  include/gf_gen/types/ego_motion.hpp
  include/gf_gen/services/ego_motion_proxy.hpp   # 极简空类也可
  CMakeLists.txt   # 可选
```

P0：按 `types[]` 生成 POD struct 头文件即可；Proxy/Skeleton 可先空壳 + TODO。  
不阻塞「第一版集成 = compose 成功」。

---

## 4. `compose` 管道（对着 afc_with_uss 写死）

### 4.1 路径解析

`project.yaml` 内相对路径均相对 **project 文件所在目录**：

| project 字段 | afc_with_uss 实际文件 |
|--------------|----------------------|
| `oem.dbc` | `oem/oem_import.dbc` |
| `oem.manifest` | `oem/oem_import.yaml` |
| `integration.wiring` | `integration/wiring.yaml` |
| `delivery.req` | `req.yaml` |
| `base` | 相对 **repo root**：`schemas/examples/desktop_ap_only.sor.json` |
| `out` | 默认写到 project 目录下 `gf.sor.json`（或 `--out`） |
| `lineage.report` | `reports/signal_lineage_report.yaml` |

wiring 里 `modules[].hpp` 若以 `projects/` 开头 → 相对 **repo root**；若相对路径 → 相对 project 目录。

### 4.2 步骤详解

```text
load_project
  → load_base_sor          # deep copy JSON
  → import_oem             # overlay
  → parse_all_hpp          # from wiring.modules
  → apply_wiring           # deployments/bindings/dataflows/services
  → merge_req              # topology, product_variants 摘要, acceptance 元数据
  → normalize_ids          # semantic.X vs services.semantic.X 统一
  → write_sor
  → lineage_check → write report → exit code
```

#### Step：`import_oem`

1. `cantools.database.load_file(dbc)`  
2. 读 manifest：`extraction.dbc.include_messages` / `exclude_name_patterns` / `module_owned` / `gateway.provides`  
3. 对 include 中的每条消息：  
   - 写入 `imports_meta.sources`  
   - 为 gateway 提供的 semantic 生成/合并 `adapter_mappings`（P0 可用「消息名 → 服务」级映射，字段级可先抄 DBC signal 名）  
4. `module_owned`：**不要**为 gateway 生成这些消息的 mapping；在 `imports_meta` 记 `owned_by: sensing.uss`  
5. 若 `P_VEHICLE_INFO` in include → 确保存在 `types.EgoMotion` 占位（字段可从 hpp 再精化）

#### Step：`parse_hpp`

P0 简易解析（禁止上 libclang）：

```text
跳过 // 与 /* */ 注释
匹配：struct Name { ... };
在大括号内匹配字段行：
  Type name;
  Type name[N];
支持类型：uint8_t/uint16_t/uint32_t/uint64_t/int*_t/float/double/bool 以及已见 struct 名
忽略：enum class、using、模板、#include、namespace 行（namespace 可剥掉）
```

输出内部结构：

```python
{"name": "UssZones", "fields": [{"name": "timestamp_ns", "type": "uint64"}, ...]}
```

映射到 SOR：

```json
{ "id": "types.UssZones", "kind": "struct", "fields": [ {"name":"timestamp_ns","type":"uint64"}, ... ] }
```

C 类型 → SOR 类型名建议表：`uint8_t`→`uint8`，`float`→`float32`，`double`→`float64`。

单测：对 `interfaces/uss_sensing/io_types.hpp`、`perception_front/io_types.hpp` 能抽出 `UssZones`、`FrontObjectList`。

#### Step：`apply_wiring`

1. 复制 `deployments` → SOR `deployments`（字段名对齐：process / provides / requires / compute_domain / package）  
2. `dataflows` → SOR `dataflows`  
3. 由 `bindings` + 已解析 types：  
   - 确保 `services[]` 中有 `services.semantic.<Name>`，`type_ref` = `types.<Struct>`  
   - 确保 `semantic_services[]` 有对应 id  
4. 无 hpp 的 process（如 `planning.driving`）：  
   - 仍写入 deployments  
   - 若 provides `Trajectory` 且 types 中无：插入 **最小占位** `types.Trajectory`（空 fields 或固定几个字段），并在 lineage 打 warning `placeholder_type`  

#### Step：`merge_req`

从 `req.yaml` 写入 SOR（建议放 `product_variants[0]` 或顶层扩展字段，P0 固定一种）：

```json
"product_variants": [{
  "id": "<req.variant>",
  "topology": "<req.topology>",
  "runtime_modules": [...],
  "bindings": ["iceoryx"],
  "capabilities": [...]
}]
```

`acceptance` 可放入 `imports_meta.acceptance` 或顶层 `acceptance`（若 schema 不允许额外字段，则只用于 lineage，不写进 SOR）。  
**jsonschema 当前较松**，额外字段一般可保留；若校验失败再收紧写入集。

#### Step：`normalize_ids`

统一约定（写进代码常量）：

| 场景 | 形式 |
|------|------|
| deployments provides/requires、dataflows.service | `services.semantic.EgoMotion` |
| bindings.service（wiring 里短写） | `semantic.EgoMotion` → 补全为 `services.semantic.EgoMotion` |
| semantic_services[].id | `semantic.EgoMotion` |
| types[].id | `types.EgoMotion` |

#### Step：`lineage_check`

对 afc_with_uss 输出 YAML：

```yaml
project_id: afc_with_uss
ok: true
errors: []
warnings: []
checks:
  - id: requires_have_provider
    status: pass
  - id: dataflow_endpoints
    status: pass
  - id: required_services_present
    status: pass
  - id: module_owned_not_on_gateway
    status: pass
```

规则：

1. **requires_have_provider**：每个 deployment.requires 的 service，至少被一个 deployment.provides  
2. **dataflow_endpoints**：from/to ∈ process 集合；service 被 from provide 且被 to require（P0 可先只查 process 存在）  
3. **required_services_present**：`req.acceptance.required_services` ⊆ SOR services[].id  
4. **module_owned_not_on_gateway**：manifest module_owned 的 semantic 不应出现在 gateway 的 provides 里（afc 中 gateway 只 provide EgoMotion → 应 pass）  

`project.lineage.fail_on_error: true` 时，`errors` 非空 → 进程退出码 1（仍写出 report 与 SOR，便于调试；或 `--no-write-on-fail` 可选）。

---

## 5. 期望的 afc_with_uss 输出形态（验收对照）

compose 成功后，SOR 中**至少**包含：

| 类别 | 内容 |
|------|------|
| types | `types.EgoMotion`、`types.UssZones`、`types.FrontObjectList`（及嵌套）、`types.Trajectory`（可占位） |
| services | `services.semantic.EgoMotion` / `UssZones` / `FrontObjectList` / `Trajectory` |
| deployments | 四个 process：gateway、sensing.uss、perception.front、planning.driving |
| dataflows | 与 wiring 五条边一致（或等价） |
| imports_meta | dbc 路径、module_owned 摘要 |

进程图（与走查一致）：

```text
adapter.vehicle_can_gateway ─EgoMotion─► sensing.uss ─UssZones─► perception.front ─FrontObjectList─► planning.driving
```

---

## 6. 验收清单（打勾即第一版集成工具侧完成）

- [ ] `pip install -e tools/codegen` 后 `gf-codegen --help` 可用  
- [ ] `gf-codegen lint projects/oem_b/adc_full/golden/gf.sor.json` 退出 0  
- [ ] `gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml` 退出 0  
- [ ] 生成 `projects/oem_a/afc_with_uss/gf.sor.json`（或 `--out` 指定路径）  
- [ ] 生成 `projects/oem_a/afc_with_uss/reports/signal_lineage_report.yaml`，`ok: true`  
- [ ] `pytest tools/codegen/tests` 全绿  
- [ ] 人工审 SOR 后复制为 `projects/oem_a/afc_with_uss/golden/gf.sor.json`，更新 `req.yaml` 的 `sor_golden`  
- [ ] README / 走查中的命令与真实 CLI 一致  

---

## 7. 推荐编码顺序（打开编辑器就按这个做）

| 序 | 文件 | 完成标准 |
|----|------|----------|
| 1 | `pyproject.toml` + `cli.py` stub | A1 |
| 2 | `schema_load.py` + `lint_cmd.py` + `test_lint_golden.py` | A2 |
| 3 | `paths.py` + `compose/load_project.py` | 能打印解析后的绝对路径 |
| 4 | `compose/parse_hpp.py` + `test_parse_hpp.py` | 抽出 UssZones / FrontObjectList |
| 5 | `compose/import_oem.py` | cantools 读 dbc + 应用 include/module_owned |
| 6 | `compose/apply_wiring.py` + `merge_req.py` | 内存中拼出完整 dict |
| 7 | `compose/lineage.py` + `write_sor.py` + `pipeline.py` | A3 端到端 |
| 8 | `test_compose_afc_with_uss.py` | CI 级锁定 |
| 9 | `suggest_cmd.py` | A4 |
| 10 | `generate_cmd.py` | A5 |

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| hpp 解析太脆 | 只支持当前 interfaces 风格；单测钉死；失败时报文件名+行号 |
| base SOR 与 AFC 语义冲突 | compose 以 wiring 覆盖 deployments；base 只提供 schema_version/空壳 |
| Trajectory 无 hpp | 占位 type + warning，不阻塞 |
| cantools 版本差异 | 在 `versions.lock.md` / pyproject 钉下限 |
| 路径 Windows/Linux | 统一 `pathlib`；测试在 Linux CI |

---

## 9. 下一步

1. **评审本文**（尤其 §4 ID 约定与 lineage 四条）  
2. 同意后开干：**先 A1+A2，再 A3 打通 afc_with_uss**  
3. A3 通过后再补 golden / suggest / generate  

实现开始时，在本文件顶部把「代码尚未落地」改为版本与日期，并在 `P0_PLAN.md` 轨 A 勾选进度。
