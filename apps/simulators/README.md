# apps/simulators

Semantic-level **stubs** so the platform runs without external production component repos.

| Simulator | Publishes (example) |
|-----------|---------------------|
| [perception_feed](perception_feed/) | `semantic.ObjectList` |
| [planning_feed](planning_feed/) | `semantic.Trajectory` (optional) |
| [cp_ipc_peer](cp_ipc_peer/) | MCU CP IPC peer for gateway testing |

Switch to production: change SOR `product_variants[].components[].package` only.

Parent: [apps/README.md](../README.md)
