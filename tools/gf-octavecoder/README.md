# gf-octavecoder（含 gf_octave_planning）

领域内 Octave→C++ **窄**转译 + 规划算子库。  
**不是**通用 Octave 编译器；与 **`gf-codegen` 零耦合**。

## install / 入口

与 `gf-config` / `gf-codegen` 相同：editable 安装后直接跑命令。

```bash
pip install -e tools/gf-octavecoder
gf-octavecoder generate --sku afc
```

`python -m gf_octavecoder` 仅作未安装时的兜底（`compile_sil` 也会提示）。

## 和 `gf_planning_driving` 的关系

```text
gf_planning_driving
  ├── src/main.cpp                      ← 手写薄壳（iceoryx Take/Send）
  ├── oct_gen/*.cpp                     ← .m 生成（gitignore）
  └── gf_octave_planning (ops/)         ← 手写算子；.m 白名单调用
```

## 目录

```text
octave_planning/{afc,adc,common}/       ← 只放 .m
tools/gf-octavecoder/
  ops/include/gf_octave_planning/
  ops/src/
  src/                                  ← CLI / 转译器
projects/<sku>/apps/planning/driving/
  oct_gen/                              ← 直接生成至此（无拷贝）
```

## 原则（摘要）

1. **独立函数**：手刹/夹紧/跟车/AEB 等拆开，便于复用与单测。  
2. **一一对应**：`.m` 是算法真源；C 是对应实现，禁止漂移。  
3. **防按下葫芦浮起瓢**：单点抽取 + 金向量；不顺手改 gateway/BEV/EM。

## compile

`.m` 更新 → `gf-octavecoder generate` 写 `oct_gen/` → cmake 编进 `gf_planning_driving`（mtime；**不** cp）。

## BEV / 通信

前 120/130 m，后 60 m；AFC 无 USS；终态 iceoryx + GfChannel（JSON 控车另阶段删除）。
