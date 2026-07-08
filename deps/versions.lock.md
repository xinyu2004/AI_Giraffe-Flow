# Dependency version lock (human readable)

> Pins are **TBD** until Phase 1 integration. When a library is introduced, record **exact tag or git SHA** here and mirror in CMake/`third_party`.

| ID | Planned pin | Introduced in | Owner | Notes |
|----|-------------|---------------|-------|-------|
| iceoryx | TBD | Phase 1 | middleware/com | |
| vsomeip | TBD | Phase 1 | bindings/someip | Watch Boost |
| cyclonedds | TBD | Phase 1 | bindings/dds | |
| cyclonedds_cxx | TBD | Phase 1 | bindings/dds | |
| nlohmann_json | TBD | Phase 0/1 | schemas + tools | Prefer header-only |
| yaml_cpp | TBD | Phase 0 tools | tools/importer | Host only |
| cli11 | TBD | Phase 0 tools | tools/* | Host only |
| spdlog | TBD | optional | middleware/log | |
| gtest | TBD | CI | tests | Host only |
| boost | TBD | with vsomeip | platform | Prefer BSP package |
| openvx | TBD | Phase 3 | apps/perception | SoC-specific |

## Upgrade checklist

1. Update `DEPENDENCIES.yaml` purpose/notes if needed  
2. Set pin in this file (tag/SHA)  
3. Update CMake FetchContent / submodule once build exists  
4. Run license scan + board link test if `runtime_board`  
5. Note breaking changes in PR description  

## License snapshot

Full SPDX list lives in `DEPENDENCIES.yaml`. Aggregate NOTICE generation is future work under `third_party/NOTICE` (planned).
