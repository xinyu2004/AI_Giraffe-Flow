% Demo acceptance cal. Numbers live here. Algorithms only read this struct.
% C++ plan_cal.hpp is generated later — do not keep hpp in lockstep until Host signs off.

function p = gf_plan_cal()
  %% Corridor (lat, ego-frame y) — weights, not ACC/AEB modes
  p.lat_acc_m = 3.2;
  p.lat_aeb_m = 8.0;
  p.lat_merge_m = 1.0;
  p.lon_max_d_m = 80.0;

  %% Horizon / visibility. Recover slow, degrade fast (vis_up_alpha per tick).
  p.t_base_s = 10.0;
  p.t_plan_min_s = 1.0;
  p.d_cal_cap_m = 120.0;
  p.d_fov_conf_m = 120.0;
  p.d_fov_conf_min = 0.20;
  p.d_see_lane_bad_m = 12.0;
  p.vis_up_alpha = 0.08;
  p.d_vis_tight_m = 40.0;
  p.a_req_vis_gain = 1.25;
  p.traj_horizon_floor_m = 8.0;
  p.traj_horizon_max_m = 120.0;

  %% CPU budget: do not raise these without measuring Host tick
  p.traj_n = 16;
  p.obj_n_max = 8;

  %% Occlusion / lane-change gate (flag only; no second corridor yet)
  p.occ_w_min = 0.40;
  p.cls_truck = 2.0;
  p.t_lc_min_s = 6.0;
  p.d_lc_min_m = 40.0;
  p.lc_conf_min = 0.50;
  p.cutin_head_gain = 1.20;

  %% Kinematics (constraint scale, not a mode switch)
  p.aeb_decel_mps2 = 6.0;
  p.aeb_d_min_m = 4.5;
  p.aeb_margin_m = 2.0;
  p.aeb_react_s = 0.50;
  p.closing_min_mps = 0.3;
  p.a_req_label_acc = 0.12;
  p.a_req_label_aeb = 0.85;

  %% Cruise / execute tracking
  p.cruise_v_mps = 12.0;
  p.acc_time_gap_s = 1.7;
  p.acc_gap_min_m = 8.0;
  p.acc_gap_max_m = 80.0;
  p.acc_gap_over_stop_m = 6.0;
  p.acc_speed_db_mps = 0.25;
  p.acc_thr_gain = 0.11;
  p.acc_thr_max = 0.50;
  p.acc_thr_hold = 0.10;
  p.acc_brake_gain = 0.22;
  p.acc_brake_min = 0.08;
  p.acc_brake_max = 0.85;
  p.acc_over_v_gain = 0.28;
  p.cruise_standstill_v_mps = 0.8;
  p.cruise_thr_standstill_min = 0.42;
  p.cruise_thr_standstill_max = 0.72;
  p.hold_brake = 0.22;

  %% Lane / LKA
  p.lat_ky = 0.38;
  p.lat_kpsi = 0.65;
  p.lat_max_steer = 0.42;
  p.lat_e_sat_m = 1.8;
  p.lat_e_desense_hi_m = 1.2;
  p.lat_e_desense_lo_m = 0.6;
  p.lat_ky_scale_hi = 0.30;
  p.lat_ky_scale_lo = 0.50;
  p.lat_c1_sat = 0.40;
  p.lat_dsteer_max = 0.055;
  p.lat_ey_invalid_m = 3.0;
  p.lat_c1_invalid = 0.40;
  p.lat_ey_slow_m = 1.0;

  %% Path samples (BEV)
  p.traj_blend_m = 14.0;
  p.traj_speed_floor_mps = 0.2;
end
