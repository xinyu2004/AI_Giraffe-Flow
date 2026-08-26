% AFC path — horizon from D_see / T_plan (not mode speed_scale). 1:1 lat_traj.hpp.

function [x_m, y_m, horizon_m] = m_lat_traj(speed_mps, D_see, T_plan, lane_valid, c0, c1, c2, c3, x_end)
  p = gf_plan_cal();
  N = p.traj_n;
  use_lane = gf_lane_usable(lane_valid, c0, c1);
  v = max(speed_mps, p.traj_speed_floor_mps);
  D_plan = min([D_see, v * T_plan, p.traj_horizon_max_m]);
  if use_lane && x_end > 0.5
    D_plan = min(D_plan, x_end);
  end
  D_plan = min(D_plan, D_see);
  D_plan = max(D_plan, p.traj_horizon_floor_m);
  if D_plan > D_see
    D_plan = max(D_see, 1.0);
  end
  horizon_m = D_plan;
  ds = horizon_m / (N - 1);
  x_m = zeros(1, N);
  y_m = zeros(1, N);
  for i = 1:N
    x = ds * (i - 1);
    x_m(i) = x;
    if use_lane
      alpha = 1.0 - exp(-x / p.traj_blend_m);
      y_m(i) = alpha * lat_poly_y(x, c0, c1, c2, c3);
    else
      y_m(i) = 0.0;
    end
  end
end

function y = lat_poly_y(x, c0, c1, c2, c3)
  y = c0 + c1 * x + c2 * x * x + c3 * x * x * x;
end
