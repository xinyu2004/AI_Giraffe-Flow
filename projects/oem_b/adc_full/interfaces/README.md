# interfaces/ — 项目本地模块接口

本目录存放 **adc_full** 项目专属的 `io_types.hpp`，由外仓交付或集成工程师维护。

- 接口仅在本项目 `interfaces/` 下维护；wiring 通过 `modules[].hpp` 引用本目录路径，compose 时解析。
- Golden SOR 见 `../golden/gf.sor.json`。
