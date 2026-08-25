# GfChannel

**General** POSIX shared-memory channel between **non-Giraffe** (or driver) processes and Giraffe — **not** iceoryx, and **not** image-only.

| Use | Slot example | Format |
|-----|--------------|--------|
| Camera plane | `gf.channel.front` | nv12 / … |
| Vehicle state (SIL host → gateway) | `gf.channel.vehicle_state` | blob (`GfVehicleStatePod`) |
| Vehicle cmd (gateway → SIL host) | `gf.channel.vehicle_cmd` | blob (`GfVehicleCmdPod`) |
| Fake perception (SIL → FCM) | `gf.channel.fake_perc` | blob (`GfFakePercPod`) |

POD layouts: [`include/gf_channel/boundary_pods.h`](include/gf_channel/boundary_pods.h).

**iceoryx** is only for Giraffe-internal semantic services (EgoMotion, Perception_*, Trajectory, …).

CMake target: `gf_channel` / `gf_channel::channel`.
