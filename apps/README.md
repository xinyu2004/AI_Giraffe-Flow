# apps/

Reference processes for integration tests — **not customer production algorithms**.

## Layout

| Dir | Role |
|-----|------|
| [adapters/](adapters/) | Input boundary: sensors, CAN gateway, **mcu.cp_gateway** |
| [simulators/](simulators/) | Semantic output stubs when external repos absent |
| [demo_pipeline/](demo_pipeline/) | End-to-end wiring |

## Production components

Perception / planning / control **ship in external repos**. SOR `components[].package` selects sim vs production.

## Legacy top-level dirs

`radar`, `perception`, `planning`, `control`, `ivi` remain as migration references — prefer `adapters/` + `simulators/`.

Parent: [component-composition.md](../docs/en/architecture/component-composition.md)
