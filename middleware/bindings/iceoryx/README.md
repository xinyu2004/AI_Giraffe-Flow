# iceoryx binding

Static platform binding for Eclipse iceoryx classic (pin: [versions.lock.md](../../../deps/versions.lock.md)).

```bash
bash scripts/bootstrap_deps.sh
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build -j"$(nproc)"
bash scripts/run_iox_demo.sh
```

API: `gf_ara::com::binding::iceoryx::{InitRuntime,EventPublisher,EventSubscriber}`

Parent: [../README.md](../README.md)
