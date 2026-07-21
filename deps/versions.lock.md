# versions.lock.md

Pin exact versions here after spikes. Edit [DEPENDENCIES.yaml](DEPENDENCIES.yaml) first.

| id | version / SHA | phase | consumer | notes |
|----|---------------|-------|----------|-------|
| attr | **2.5.2** | P0 | middleware/.deps-prefix（acl 依赖） | 源码；`bootstrap_deps.sh` |
| acl | **2.3.2** | P0 | iceoryx / middleware/.deps-prefix | 源码；交叉用 `GF_CROSS_PREFIX` |
| iceoryx | **v2.0.8** | P0 | middleware/bindings/iceoryx | classic C++; 同工具链 add_subdirectory |
| vsomeip | **stub** (P1 staged) | P1 | middleware/bindings/someip | 真 vsomeip+Boost 后置；`GF_WITH_SOMEIP` |
| cyclonedds | **0.10.5** | P2 | middleware/bindings/dds | `bootstrap_deps.sh` 拉取；`smoke_bd_cyclone.sh` 真收发；主链仍 iceoryx；P2-G 已钉扎 |
| cyclonedds_cxx | TBD | P1 | middleware/bindings/dds | 可选 C++ 绑定后置 |
| nlohmann_json | TBD | P0 | middleware, tools | |
| cli11 | TBD | P0 | gf-codegen, gmt | |
| mcap | TBD | P2 | gmt/measure | |
| cantools | TBD | P1 | gf-codegen import | Python |
| rauc | TBD | P2 | middleware/ucm | not SWUpdate |
| doip_cpp | TBD | P1 | middleware/diag | candidate |
