# CI

| Script | Purpose |
|--------|---------|
| [scripts/smoke.sh](scripts/smoke.sh) | bootstrap → pytest → compose(afc+adc) → cmake/ctest → smoke_sil → optional aarch64 link |

```bash
bash ci/scripts/smoke.sh
```

P0 收口验收入口。Board jobs must not pull host-only UI/ROS deps — see [deps/README.md](../deps/README.md).
