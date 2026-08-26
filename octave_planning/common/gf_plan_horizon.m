% Sight + plan time. Optional: D_occ, D_fov, prev (fall fast, rise slow).
function [D_see, T_plan] = gf_plan_horizon(v, lane_valid, e_y, c1, x_end, ...
                                          D_occ, D_fov, D_see_prev, T_plan_prev)
  p = gf_plan_cal();
  if nargin < 6 || isempty(D_occ)
    D_occ = p.d_cal_cap_m;
  end
  if nargin < 7 || isempty(D_fov)
    D_fov = p.d_fov_conf_m;
  end
  if nargin < 8 || isempty(D_see_prev)
    D_see_prev = 0.0;
  end
  if nargin < 9 || isempty(T_plan_prev)
    T_plan_prev = 0.0;
  end

  D_vr = p.d_cal_cap_m;
  if gf_lane_usable(lane_valid, e_y, c1)
    if x_end > 0.5
      D_vr = x_end;
    end
  else
    D_vr = min(D_vr, p.d_see_lane_bad_m);
  end

  D_raw = min([D_fov, D_vr, D_occ, p.d_cal_cap_m]);
  D_see = gf_plan_vis_slew(D_raw, D_see_prev, p.vis_up_alpha);

  T_raw = min(p.t_base_s, D_see / max(v, p.traj_speed_floor_mps));
  T_raw = max(T_raw, p.t_plan_min_s);
  T_plan = gf_plan_vis_slew(T_raw, T_plan_prev, p.vis_up_alpha);
end
