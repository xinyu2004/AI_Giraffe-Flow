% AFC lateral trajectory (fixed N=16) — 1:1 with gf_octave_planning/lat_traj.hpp.

function [x_m, y_m, horizon_m] = m_lat_traj(speed_mps, speed_scale, lane_valid, c0, c1, c2, c3, x_end)
  N = 16;
  blend = 18.0;
  speed = max(speed_mps * speed_scale, 0.2);
  if lane_valid
    x_cap = x_end;
  else
    x_cap = 100.0;
  end
  horizon_m = gf_clamp(speed * 4.0, 25.0, min(100.0, x_cap));
  ds = horizon_m / (N - 1);
  x_m = zeros(1, N);
  y_m = zeros(1, N);
  for i = 1:N
    x = ds * (i - 1);
    x_m(i) = x;
    if lane_valid
      alpha = 1.0 - exp(-x / blend);
      y_m(i) = alpha * lat_poly_y(x, c0, c1, c2, c3);
    else
      y_m(i) = 0.0;
    end
  end
end

function y = lat_poly_y(x, c0, c1, c2, c3)
  y = c0 + c1 * x + c2 * x * x + c3 * x * x * x;
end
