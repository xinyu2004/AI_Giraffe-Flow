# apps/adapters

Input-boundary processes: OEM signals, sensor SDKs, **MCU CP IPC gateway**.

| Adapter | Role |
|---------|------|
| [radar](../radar/) | Radar SDK → semantic (move note: reference lives here) |
| [camera_ingest](../camera_ingest/) | Camera ingest |
| [vehicle_motion_gateway](../vehicle_motion_gateway/) | Shared vehicle signals (fan-out) |
| [mcu_cp_gateway](mcu_cp_gateway/) | AP ↔ AUTOSAR CP over IPC (**zero gf code on MCU**) |

Legacy top-level `apps/radar` etc. remain during migration; new work targets `adapters/`.

Parent: [apps/README.md](../README.md)
