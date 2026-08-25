% AFC longitudinal ACC/AEB — gold algorithm (1:1 with gf_octave_planning/lon_acc_aeb.hpp).
% Independent helpers for reuse; steer/lateral stays in planning shell.

function ctrl = m_lon_acc_aeb(v, lead_valid, d, rel)
  v = max(0.0, v);
  if ~lead_valid
    ctrl = lon_cruise(v);
    return;
  end
  closing = max(0.0, -rel);
  if closing > 0.5
    ttc = d / closing;
  else
    ttc = 1.0e6;
  end
  if d < 5.0 || (v > 1.2 && (d < 10.0 || ttc < 1.4))
    ctrl = lon_aeb(v, d, ttc);
    return;
  end
  desired_gap = gf_clamp(max(8.0, v * 1.6), 8.0, 40.0);
  gap_err = d - desired_gap;
  if v < 1.0 && d > 10.0
    ctrl = lon_pullaway(v, d, rel, gap_err);
    return;
  end
  ctrl = lon_acc_follow(v, d, rel);
end

function ctrl = lon_cruise(v)
  ctrl.mode = 'cruise';
  ctrl.target_speed_mps = 12.0;
  err = ctrl.target_speed_mps - v;
  if v < 0.8
    ctrl.throttle = gf_clamp(0.45 + err * 0.05, 0.40, 0.75);
    ctrl.brake = 0.0;
  else
    ctrl.throttle = gf_clamp(0.2 + err * 0.08, 0.0, 0.7);
    if err < -2.0
      ctrl.brake = gf_clamp((-err - 2.0) * 0.1, 0.0, 0.4);
    else
      ctrl.brake = 0.0;
    end
  end
end

function ctrl = lon_aeb(v, d, ttc)
  ctrl.mode = 'aeb';
  ctrl.target_speed_mps = 0.0;
  ctrl.throttle = 0.0;
  if d < 5.0 || ttc < 1.0
    ctrl.brake = 1.0;
  else
    ctrl.brake = gf_clamp(0.55 + (10.0 - d) * 0.05, 0.55, 1.0);
  end
end

function ctrl = lon_pullaway(v, d, rel, gap_err)
  ctrl.mode = 'pullaway';
  pull = gf_clamp(8.0 + gap_err * 0.2 + rel * 0.3, 6.0, 12.0);
  ctrl.target_speed_mps = pull;
  ctrl.throttle = gf_clamp(0.42 + (pull - v) * 0.06, 0.35, 0.75);
  ctrl.brake = 0.0;
end

function ctrl = lon_acc_follow(v, d, rel)
  ctrl.mode = 'acc';
  desired_gap = gf_clamp(max(8.0, v * 1.6), 8.0, 40.0);
  gap_err = d - desired_gap;
  ctrl.target_speed_mps = gf_clamp(v + gap_err * 0.15 + rel * 0.4, 0.0, 16.0);
  speed_err = ctrl.target_speed_mps - v;
  if speed_err >= 0.0
    ctrl.throttle = gf_clamp(0.15 + speed_err * 0.1, 0.0, 0.65);
    ctrl.brake = 0.0;
  else
    ctrl.throttle = 0.0;
    ctrl.brake = gf_clamp((-speed_err) * 0.12, 0.0, 0.7);
  end
end
