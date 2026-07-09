# 可组合组件与外部量产仓

- 平台 monorepo：**adapters** + **simulators** + middleware
- 量产感知/规划/控制：**外部仓**，SOR `components[].package` 切换
- 无外部仓时：`simulators/perception_feed` 发布 `semantic.ObjectList`

切换 SKU：只改 SOR `product_variants`，不改规划业务代码。

见 [DESIGN.md §6](DESIGN.md)。
