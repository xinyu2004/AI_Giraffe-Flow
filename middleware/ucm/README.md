# middleware/ucm

ARA-inspired **Update and Configuration Management** (`gf_ara::ucm`) — simplified OTA skeleton.

| Piece | Role |
|-------|------|
| `include/gf_ara/ucm/` | Public API placeholders |
| `include/gf/ucm/` | Internal hooks (package transfer, partition callbacks) |

**P1 skeleton** — no implementation yet. Cooperates with `sm` (degraded mode during update) and `phm` (supervision pause).

Enable via SOR `runtime_modules[]` and deploy profile. OTA backend candidates: RAUC, OSTree (see [THIRD_PARTY_EVALUATION.md](../../docs/en/dependencies/THIRD_PARTY_EVALUATION.md)); **not** SWUpdate.

Parent: [middleware/README.md](../README.md)
