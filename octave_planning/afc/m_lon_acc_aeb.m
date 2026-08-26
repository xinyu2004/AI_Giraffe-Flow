% Thin wrapper: single-lead → m_plan_tick. Host should call m_plan_tick directly.

function ctrl = m_lon_acc_aeb(v, lead_valid, d, rel, lead_lat_m, e_y, c1, lane_valid)
  if nargin < 5
    lead_lat_m = 0.0;
  end
  if nargin < 6
    e_y = 0.0;
  end
  if nargin < 7
    c1 = 0.0;
  end
  if nargin < 8
    lane_valid = 1.0;
  end
  obj = [];
  if lead_valid
    obj = [d, rel, lead_lat_m, 4.5, 1.0, 0.0, 0.0];
  end
  out = m_plan_tick(v, 0.0, lane_valid, e_y, e_y, c1, 0.0, 0.0, 1.0e6, ...
                    1.0, 1.0, obj, 0.0, 0.0);
  ctrl.throttle = out.throttle;
  ctrl.brake = out.brake;
  ctrl.mode = out.mode;
  ctrl.target_speed_mps = out.target_speed_mps;
end
