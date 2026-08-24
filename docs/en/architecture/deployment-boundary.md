# Deployment boundary

Vehicle delivery and deploy knobs live in **`req.yaml`** (no separate `deploy/profile.yaml`).

- Example: [`projects/afc/req.yaml`](../../../projects/afc/req.yaml)
  - Contract: `topology` / `bindings` / `runtime_modules` / `acceptance`
  - Cut-down: `observability` / `apps` (reference process list)
- Host vs cross / where it runs: project `scripts/` (`compile_sil` / `compile_hil`)
- Facelift: copy `projects/<oem>/<product>/` and edit `req.yaml` in the copy

See [DESIGN.md §7](DESIGN.md) · [projects/README.md](../../../projects/README.md)
