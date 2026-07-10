# bindings/ (under middleware)

Transport plugins behind `gf_ara::com`.

| Binding | Transport | Dep id |
|---------|-----------|--------|
| [iceoryx](iceoryx/) | On-SoC zero-copy | `iceoryx` |
| [someip](someip/) | SOME/IP (vsomeip) | `vsomeip` |
| [dds](dds/) | DDS (CycloneDDS) | `cyclonedds` |
| [cross_domain_ipc](cross_domain_ipc/) | AP ↔ MCU CP | gateway process |

Parent: [../README.md](../README.md) · Deps: [../../deps/DEPENDENCIES.yaml](../../deps/DEPENDENCIES.yaml)
