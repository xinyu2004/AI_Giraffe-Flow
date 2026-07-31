# apps/adapters

Input-boundary processes: OEM signals, sensor SDKs, **MCU CP IPC gateway**.

| Adapter | Role |
|---------|------|
| [mcu_cp_gateway](mcu_cp_gateway/) | AP ↔ AUTOSAR CP over IPC (**zero gf code on MCU**) |
| [radar](../radar/) | Radar SDK → semantic (legacy reference) |
| [camera_ingest](../camera_ingest/) | Camera ingest |
| [vehicle_motion_gateway](../vehicle_motion_gateway/) | Shared vehicle signals (fan-out) |

SKU CAN gateway stub for `afc_with_uss`:
[`projects/oem_a/afc_with_uss/apps/adapters/vehicle_can_gateway/`](../../projects/oem_a/afc_with_uss/apps/adapters/vehicle_can_gateway/).

Parent: [apps/README.md](../README.md)
