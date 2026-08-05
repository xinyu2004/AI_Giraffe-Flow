# apps/

Reference processes for integration tests — **not customer production algorithms**.

## Layout

| Dir | Role |
|-----|------|
| [common/](common/) | Shared demo headers (e.g. `uss_zones_topic`) |
| [adapters/](adapters/) | Shared adapters (e.g. `mcu_cp_gateway`); SKU CAN gateway lives under project |
| [simulators/](simulators/) | Semantic output stubs when external repos absent |
| [demo_pipeline/](demo_pipeline/) | End-to-end wiring demo |

Process bring-up (Offer→Running + FG + PHM/Collector/Log) lives in [`middleware/runtime/`](../middleware/runtime/) (`gf_ara::runtime`).

Tap / inject live in [`tools/debug_bridge/`](../tools/debug_bridge/).

## SKU stubs

Product-specific stubs (gateway / sensing / perception / planning for a given OEM SKU) live under:

`projects/<oem>/<sku>/apps/`

Example: [projects/oem_a/afc_with_uss/apps/](../projects/oem_a/afc_with_uss/apps/).

## Production components

Perception / planning / control **ship in external repos**. SOR `components[].package` selects sim vs production.

## Legacy top-level dirs

`radar`, `perception`, `planning`, `control`, `ivi` remain as migration references — prefer project `apps/` + shared `adapters/` / `simulators/`.

Parent: [component-composition.md](../docs/en/architecture/component-composition.md)
