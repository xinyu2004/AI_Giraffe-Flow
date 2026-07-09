# middleware/diag

ARA-inspired **Diagnostics** (`gf_ara::diag`) — **DoIP-first** skeleton.

| Piece | Role |
|-------|------|
| `include/gf_ara/diag/` | Public DoIP / UDS type placeholders |
| `transport/doip/` | DoIP binding implementation (later) |

**P1 skeleton** — vehicle identification, routing activation, diagnostic TCP/UDP channel abstraction.

Enable via `runtime_modules[]`. Third-party candidates: doip-cpp, minimal in-tree stack (see dependency evaluation).

Parent: [middleware/README.md](../README.md)
