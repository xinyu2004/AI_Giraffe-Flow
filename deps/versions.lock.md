# versions.lock.md

Pin exact versions here after spikes. Edit [DEPENDENCIES.yaml](DEPENDENCIES.yaml) first.

| id | version / SHA | phase | consumer | notes |
|----|---------------|-------|----------|-------|
| attr | **2.5.2** | P0 | middleware/.deps-prefix（acl 依赖） | 源码；`bootstrap_deps.sh` |
| acl | **2.3.2** | P0 | iceoryx / middleware/.deps-prefix | 源码；交叉用 `GF_CROSS_PREFIX` |
| iceoryx | **v2.0.8** | P0 | middleware/bindings/iceoryx | classic C++; 同工具链 add_subdirectory |
| vsomeip | TBD | P1 | middleware/bindings/someip | Boost |
| cyclonedds | TBD | P1 | middleware/bindings/dds | incl. idlc |
| cyclonedds_cxx | TBD | P1 | middleware/bindings/dds | |
| nlohmann_json | TBD | P0 | middleware, tools | |
| cli11 | TBD | P0 | gf-codegen, gmt | |
| mcap | TBD | P2 | gmt/measure | |
| cantools | TBD | P1 | gf-codegen import | Python |
| rauc | TBD | P2 | middleware/ucm | not SWUpdate |
| doip_cpp | TBD | P1 | middleware/diag | candidate |
