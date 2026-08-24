# gf-octavecoder（含 gf_octave_planning）

领域内 Octave→C++ 窄转译 + 规划算子库。  
**不是**通用 Octave 编译器；与 **`gf-codegen` 零耦合**。

## 和 `gf_planning_driving` 的关系

最终进程/二进制仍是 **`gf_planning_driving`**（`planning.driving`）。

```text
gf_planning_driving
  ├── src/main.cpp                         ← 手写薄壳
  ├── oct_gen/*.cpp                        ← Octave 生成（gitignore）
  └── lib / objects: gf_octave_planning    ← 手写算子（本树 ops/）
```

**`gf_octave_planning`**：库名/命名空间，不是独立进程。

## 目录

```text
octave_planning/{afc,adc,common}/     ← 只放 .m
tools/gf-octavecoder/
  ops/include/gf_octave_planning/     ← 算子头
  ops/src/
projects/<sku>/apps/planning/driving/
  src/main.cpp
  oct_gen/                            ← 直接生成至此（无拷贝）
```

## compile

`.m` 更新 → octavecoder 写 `oct_gen/` → cmake 编进 `gf_planning_driving`。

## BEV / 通信

前 120/130 m，后 60 m；无 USS；iceoryx + GfChannel；无 JSON IPC。
