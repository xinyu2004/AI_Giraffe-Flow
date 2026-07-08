# bindings/

Transport plugins behind `gf_ara::com` / `gf::com`.

| Binding | Transport | Dep id (`deps/DEPENDENCIES.yaml`) |
|---------|-----------|-------------------------------------|
| [iceoryx](iceoryx/) | On-SoC zero-copy | `iceoryx` |
| [someip](someip/) | SOME/IP (vsomeip) | `vsomeip` |
| [dds](dds/) | DDS (CycloneDDS) | `cyclonedds`, `cyclonedds_cxx` |

Selection via SOR / manifest / `COM_BINDING` (planned).
