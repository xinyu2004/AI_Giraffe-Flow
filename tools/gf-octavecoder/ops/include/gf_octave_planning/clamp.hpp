#pragma once

// Hand-written operators linked into gf_planning_driving.
// Namespace / product name: gf_octave_planning
// (Octave gold → oct_gen/*.cpp calls these; not a separate process.)

namespace gf_octave_planning {

inline float clamp(float x, float lo, float hi) {
  return x < lo ? lo : (x > hi ? hi : x);
}

}  // namespace gf_octave_planning
