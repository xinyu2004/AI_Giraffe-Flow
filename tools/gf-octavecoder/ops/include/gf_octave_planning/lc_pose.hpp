#pragma once

#include "gf_octave_planning/plan_cal.hpp"

#include <cmath>

// 1:1 octave_planning/common/gf_lc_pose.m
// Planning state. Paint is the map; DR increment only while paint is gone.

namespace gf_octave_planning {

struct LcPose {
  int have{0};
  int remapped{0};
  int paint_ok{0};
  float y{0.0f};
  float psi{0.0f};
  float e_y{0.0f};
  float y_dr{0.0f};
  float psi_dr{0.0f};
};

inline LcPose gf_lc_pose_zero() {
  return LcPose{};
}

inline LcPose gf_lc_pose(LcPose pose, float e_y, float c1, bool paint_ok, float W, float y_dr,
                         float psi_dr) {
  const PlanCal& p = plan_cal();
  const float y_pre = -e_y;
  const float y_post = W - e_y;
  if (paint_ok) {
    if (pose.remapped == 0 && pose.have != 0) {
      const bool closer_post =
          std::fabs(y_post - pose.y) + 0.40f < std::fabs(y_pre - pose.y);
      const bool jumped = std::fabs(e_y - pose.e_y) > p.lc_remap_ey_m;
      if (closer_post || jumped) {
        pose.remapped = 1;
      }
    }
    pose.y = (pose.remapped != 0) ? y_post : y_pre;
    pose.psi = -c1;
    pose.e_y = e_y;
  } else if (pose.have != 0) {
    pose.y = pose.y + (y_dr - pose.y_dr);
    pose.psi = pose.psi + (psi_dr - pose.psi_dr);
  } else {
    pose.y = y_dr;
    pose.psi = psi_dr;
  }
  pose.y_dr = y_dr;
  pose.psi_dr = psi_dr;
  pose.have = 1;
  pose.paint_ok = paint_ok ? 1 : 0;
  return pose;
}

}  // namespace gf_octave_planning
