# iceoryx binding

Static platform binding for Eclipse iceoryx classic (pin: [versions.lock.md](../../../dep-manifest/versions.lock.md)).

Smoke lives **here** (no `projects/`):

```bash
cmake -B build -DGF_BUILD_TESTS=ON && cmake --build build -j"$(nproc)"
ctest --test-dir build -R 'gf_iox_' --output-on-failure
# or:
bash middleware/bindings/iceoryx/testcases/run_iox_pubsub.sh
```

API: `gf_ara::com::binding::iceoryx::{InitRuntime,EventPublisher,EventSubscriber,EventWaitSet,PeriodTimer}`

- **EventWaitSet** — attach Proxy/Subscriber `HAS_DATA` (+ UserTrigger); apps `TimedWaitMs` / `Wait` instead of private `sleep`.
- **PeriodTimer** — middleware period wake for `publish_policy: period` (gateway).

Parent: [../README.md](../README.md)

