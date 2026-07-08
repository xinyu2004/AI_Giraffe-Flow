# apps/ (reference processes)

Reference SOA processes for demos and integration tests. Customer vehicle apps should live in **separate repos**.

| App | Intent |
|-----|--------|
| [radar](radar/) | Radar adapter (independent process) |
| [camera_ingest](camera_ingest/) | Camera ingest |
| [perception](perception/) | Fusion / OpenVX pipeline process |
| [planning](planning/) | Planning |
| [control](control/) | Control (shortest path) |
| [ivi](ivi/) | IVI (local or remote SoC) |
| [vehicle_motion_gateway](vehicle_motion_gateway/) | Shared signals (e.g. vehicle speed) |
| [demo_pipeline](demo_pipeline/) | End-to-end demo wiring |
