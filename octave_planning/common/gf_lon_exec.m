% Vehicle pedals / pullaway. Swap this file (or gf_plan_cal) when the car changes.
% Planning never writes throttle/brake except by calling this.
function ctrl = gf_lon_exec(v, v_plan, a_req)
  p = gf_plan_cal();
  v = max(0.0, v);
  v_plan = max(0.0, v_plan);
  a_max = max(p.aeb_decel_mps2, 0.5);
  brk_req = gf_clamp(a_req / a_max, 0.0, 1.0);
  ctrl.target_speed_mps = v_plan;
  ctrl.mode = 'cruise';
  err = v_plan - v;

  if brk_req >= p.a_req_label_aeb
    ctrl.throttle = 0.0;
    ctrl.brake = 1.0;
    ctrl.mode = 'aeb';
    return;
  end
  if brk_req >= p.a_req_label_acc
    ctrl.throttle = 0.0;
    ctrl.brake = gf_clamp(brk_req, p.acc_brake_min, 1.0);
    ctrl.mode = 'acc';
    return;
  end

  if v_plan < 0.4
    ctrl.throttle = 0.0;
    if v > 0.4
      ctrl.brake = p.hold_brake;
    else
      ctrl.brake = 0.0;
    end
    return;
  end

  if v > v_plan + p.acc_speed_db_mps
    ctrl.throttle = 0.0;
    over = v - v_plan;
    ctrl.brake = gf_clamp(over * p.acc_over_v_gain, p.acc_brake_min, p.acc_brake_max);
    ctrl.mode = 'acc';
    return;
  end

  if err >= p.acc_speed_db_mps
    if v < p.cruise_standstill_v_mps
      ctrl.throttle = gf_clamp(0.48 + err * 0.04, ...
                               p.cruise_thr_standstill_min, p.cruise_thr_standstill_max);
    else
      ctrl.throttle = gf_clamp(0.14 + err * p.acc_thr_gain, 0.0, p.acc_thr_max);
    end
    ctrl.brake = 0.0;
    return;
  end

  ctrl.throttle = p.acc_thr_hold;
  ctrl.brake = 0.0;
end
