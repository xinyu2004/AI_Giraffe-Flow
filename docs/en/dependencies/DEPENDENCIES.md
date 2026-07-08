# External dependencies (overview)

## Runtime (may ship on board)

| Library | Why |
|---------|-----|
| **iceoryx** | Zero-copy on-SoC data paths (radar/camera/fusion) |
| **vsomeip** | SOME/IP for vehicle SOA / ECU |
| **CycloneDDS (+ cxx)** | DDS for ROS 2 / cross-SoC without maintaining a second stack |
| **nlohmann/json** | SOR + manifests as JSON |

## Host tools only

| Library | Why |
|---------|-----|
| **yaml-cpp** | Human `req.yaml` / profiles |
| **CLI11** | Importer / codegen / lint CLIs |
| **GoogleTest** | Unit tests |

## Optional / later

| Library | Why deferred |
|---------|----------------|
| **spdlog** | Interim logger before DLT |
| **Boost** | Prefer BSP packages; often pulled by vsomeip |
| **OpenVX impl** | Vision pipeline + hooks; SoC-specific |
| **ROS 2 rclcpp** | Prefer DDS-direct first |
| **DLT / SQLite** | P1+ (`log` DLT mode, persistency) |

Policy: declare in `deps/DEPENDENCIES.yaml`, pin in `versions.lock.md`, keep board CI free of host UI/ROS desktop deps.
