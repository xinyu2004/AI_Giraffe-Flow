#pragma once

// Pack facade: Empty180 orch only (legacy strip/polar paths removed).

#include "fs/fs_empty180.hpp"

namespace gf_plan_fs {

template <typename NearFs, typename FsOut>
inline void FsComposeGround(float d_empty_cap_m, const NearFs* near, const FsOccSample* objs,
                            int n_obj, std::uint64_t ts_ns, FsOut* fs, const CamOptics& /*front*/,
                            const CamOptics& /*fl*/, const CamOptics& /*fr*/, const CamOptics& /*rl*/,
                            const CamOptics& /*rr*/, const CamOptics& /*rear*/,
                            const RoadEdgePoly& road_left, const RoadEdgePoly& road_right,
                            const RoadEdgePoly* hard_walls, int n_hard, const LaneBands& /*bands*/,
                            LaneEnvMode /*env_mode*/, const LcCorridor* /*lc*/,
                            const LaneClearFwd* lane_clear) {
  FsComposeEmpty180(d_empty_cap_m, near, objs, n_obj, ts_ns, fs, road_left, road_right, hard_walls,
                    n_hard, lane_clear);
}

}  // namespace gf_plan_fs
