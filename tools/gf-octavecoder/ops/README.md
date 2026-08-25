# gf_octave_planning

手写规划算子库（链进 **`gf_planning_driving`**，不是独立进程）。

路径：`tools/gf-octavecoder/ops/`（与转译器同产品树）。  
命名空间：`gf_octave_planning`。

**合同：** 每个算子对应 `octave_planning/common/`（或文档标明）中的白名单 `.m`；保持语义一致。  
复杂/非子集逻辑只在本库实现，由生成代码调用——仍是「独立函数」，不是堆进 `main.cpp`。
