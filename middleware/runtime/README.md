# middleware/runtime

SIL/HIL 共用的**进程 bring-up**库（`gf_ara::runtime`）。

每个业务进程在进入业务循环前：

1. 加载 `platform/` 下 collector / log 配置  
2. SM `EnsureGroup` + Running  
3. Exec `Offer` → `ReportExecutionState(Running)`  
4. 若 `phm.yaml` 有实体则周期 Alive + 故障回调（Collector / Log / SM / EM restart）

公开头文件：`include/gf_ara/runtime/process_bringup.hpp`  
链接目标：`gf_ara::runtime`
