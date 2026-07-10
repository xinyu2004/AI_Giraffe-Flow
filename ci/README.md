# CI

| Script | Purpose |
|--------|---------|
| [scripts/smoke.sh](scripts/smoke.sh) | bootstrap → pytest → cmake/ctest → afc_with_uss smoke_sil → optional aarch64 link |

```bash
bash ci/scripts/smoke.sh
```

Board jobs must not pull host-only UI/ROS deps — see [deps/README.md](../deps/README.md).
