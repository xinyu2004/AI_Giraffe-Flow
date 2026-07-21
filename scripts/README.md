# scripts/

Host-side / repo-wide helpers. **Project SIL/HIL** scripts live under each `projects/.../scripts/`.

| Script | Purpose |
|--------|---------|
| [bootstrap_deps.sh](bootstrap_deps.sh) | Check toolchains; build attr/acl → `middleware/.deps-prefix`; fetch iceoryx / cyclonedds |
| [run_iox_demo.sh](run_iox_demo.sh) | RouDi + uss_feed + demo_pipeline (platform demo binaries) |
| [cross_link_smoke.sh](cross_link_smoke.sh) | Optional aarch64 link of core/com/osal |
| [run_ab_loop.sh](run_ab_loop.sh) | Deprecated alias → `afc_with_uss` `smoke_sil.sh` |
| [smoke_bd_stub.sh](smoke_bd_stub.sh) | DDS/SOMEIP stub smoke |
| [smoke_bd_cyclone.sh](smoke_bd_cyclone.sh) | CycloneDDS 真收发（P2-B） |
| [collect_p2_evidence.sh](collect_p2_evidence.sh) | P2-G 证据包 / 可选刷新 golden |

Project example (SIL):

```bash
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
```

### Policy (board / cross)

`runtime_board` deps (**attr, acl, iceoryx**, …) are source-built into `middleware/.deps-prefix/` — see [deps/](../deps/) and [middleware/third_party/](../middleware/third_party/).

Pins: [deps/versions.lock.md](../deps/versions.lock.md)
