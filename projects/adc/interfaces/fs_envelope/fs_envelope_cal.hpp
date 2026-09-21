#pragma once

// ADC FS envelope — frozen after gf-config / compose confirms camera mounts.
// Optical reach (side ≈7, rear ≈35, front fov …) is computed ONCE at config
// time and emitted here as constants. Runtime fuse/Near only READ these —
// do not re-derive every tick (see fs_mounts.hpp for BEV observer load only).
// Spec: docs/zh/sku/adc/optical_mount_fs_plan.md

namespace gf_fs_envelope {

/** Empty180 bin count (2°). Replaces legacy kFsSectors=36. */
inline constexpr int kFsEmptyN = 180;

inline constexpr float kFsFrontFarCapM = 120.0f;
inline constexpr float kFsNearFrontCapM = 15.0f;

inline constexpr float kFsFrontFovDeg = 100.0f;
inline constexpr float kFsRearFovDeg = 120.0f;
inline constexpr float kFsRearCapM = 35.0f;
inline constexpr float kFsSideCapM = 7.0f;
inline constexpr float kFsEgoLengthM = 4.5f;
inline constexpr float kFsEgoHalfLengthM = 0.5f * kFsEgoLengthM;
inline constexpr float kFsEgoRearBumperX = -kFsEgoHalfLengthM;

}  // namespace gf_fs_envelope
