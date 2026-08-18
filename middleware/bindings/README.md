# bindings/ (under middleware)

Transport plugins behind `gf_ara::com`, plus image-plane shm.

| Binding | Transport | Dep id |
|---------|-----------|--------|
| [iceoryx](iceoryx/) | On-SoC zero-copy | `iceoryx` |
| [gf_channel](gf_channel/) | Image-plane shm (ingest↔FCM) | (stdlib / POSIX shm) |
| [someip](someip/) | SOME/IP (vsomeip) | `vsomeip` |
| [dds](dds/) | DDS (CycloneDDS) | `cyclonedds` |
| [cross_domain_ipc](cross_domain_ipc/) | AP ↔ MCU CP | gateway process |

Parent: [../README.md](../README.md) · Deps: [../../dep-manifest/DEPENDENCIES.yaml](../../dep-manifest/DEPENDENCIES.yaml)
