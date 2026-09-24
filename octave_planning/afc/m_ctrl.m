% Control only. 1:1 plan_tick.hpp m_ctrl.
% Track plan.v_plan / a_req / delta_ff. No second steer law — never synthesize δ.
% Hold enter: snap last to δ_ff so leftover does not slam the first S ticks.

function ctrl = m_ctrl(plan, v, steer_deg, lane_valid, e_y, c1)
  persistent prev_tgt
  v = max(0.0, v);
  if nargin < 3
    steer_deg = 0.0;
  end
  if nargin < 4
    lane_valid = 1;
  end
  if nargin < 5
    e_y = 0.0;
  end
  if nargin < 6
    c1 = 0.0;
  end
  if isempty(prev_tgt)
    prev_tgt = 0;
  end
  lon = gf_lon_exec(v, plan.v_plan, plan.a_req);
  target = 0;
  if isfield(plan, 'target')
    target = plan.target;
  end
  dff = 0.0;
  if isfield(plan, 'delta_ff')
    dff = plan.delta_ff;
  end
  if target > 0.5 && ~(prev_tgt > 0.5)
    gf_lat_cmd_last(dff);
  end
  steer = m_lat_follow(dff, steer_deg);
  prev_tgt = target;
  ego_rad = steer_deg * pi / 180.0;
  ctrl.throttle = lon.throttle;
  ctrl.brake = lon.brake;
  ctrl.steer = steer;
  ctrl.mode = lon.mode;
  ctrl.target_speed_mps = lon.target_speed_mps;
  ctrl.err_delta = ego_rad - dff;
  ctrl.err_v = v - plan.v_plan;
  ctrl.err_e = 0.0;
  ctrl.err_epsi = 0.0;
  if isfield(plan, 'e')
    ctrl.err_e = plan.e;
  end
  if isfield(plan, 'epsi')
    ctrl.err_epsi = plan.epsi;
  end
end
