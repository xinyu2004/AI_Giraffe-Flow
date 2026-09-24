% Layer: lane quality. 1:1 lc_side.hpp gf_lc_weights.
% One place for Host / Left / Right. Same formula on each.
% Edit here when "which lane is better" changes.
% Do not put enter/exit / hysteresis here — that is gf_lc_side.
% Neighbor with no land: ok=0, weight=0.

function w = gf_lc_weights(q, v, D_see)
  if nargin < 2
    v = 0.0;
  end
  if nargin < 3
    D_see = 0.0;
  end
  have_H = field_or(q, 'have_H', 1);
  d_Hf = field_or(q, 'd_H_f', 0.0);
  d_Hhard = field_or(q, 'd_H_hard', 1.0e6);
  rel_Hf = field_or(q, 'rel_H_f', 0.0);
  hdg_Hf = field_or(q, 'hdg_H_f', 0.0);
  d_Hr = field_or(q, 'd_H_r', 0.0);
  rel_Hr = field_or(q, 'rel_H_r', 0.0);
  have_L = field_or(q, 'have_L', 0);
  d_Lf = field_or(q, 'd_L_f', 0.0);
  d_Lhard = field_or(q, 'd_L_hard', 1.0e6);
  rel_Lf = field_or(q, 'rel_L_f', 0.0);
  hdg_Lf = field_or(q, 'hdg_L_f', 0.0);
  d_Lr = field_or(q, 'd_L_r', 0.0);
  rel_Lr = field_or(q, 'rel_L_r', 0.0);
  have_R = field_or(q, 'have_R', 0);
  d_Rf = field_or(q, 'd_R_f', 0.0);
  d_Rhard = field_or(q, 'd_R_hard', 1.0e6);
  rel_Rf = field_or(q, 'rel_R_f', 0.0);
  hdg_Rf = field_or(q, 'hdg_R_f', 0.0);
  d_Rr = field_or(q, 'd_R_r', 0.0);
  rel_Rr = field_or(q, 'rel_R_r', 0.0);

  w.ok_H = have_H ~= 0;
  w.H = 0.0;
  if w.ok_H
    % Front only. Host rear must not invite leave-after-pass.
    w.H = lc_quality(d_Hf, gf_plan_cal().d_lc_min_m, 0.0);
  end
  leave = gf_lc_host_ok(d_Hf, rel_Hf, hdg_Hf, v, d_Hhard);
  w.ok_L = leave && gf_lc_can(have_L, d_Lf, d_Lr, rel_Lr, v, D_see, d_Lhard, rel_Lf, hdg_Lf);
  w.L = 0.0;
  if w.ok_L
    w.L = lc_quality(d_Lf, d_Lr, rel_Lr);
  end
  w.ok_R = leave && gf_lc_can(have_R, d_Rf, d_Rr, rel_Rr, v, D_see, d_Rhard, rel_Rf, hdg_Rf);
  w.R = 0.0;
  if w.ok_R
    w.R = lc_quality(d_Rf, d_Rr, rel_Rr);
  end
end

function s = lc_quality(d_f, d_r, rel_r)
  p = gf_plan_cal();
  d_f = min(max(0.0, d_f), p.d_cal_cap_m);
  d_r = min(max(0.0, d_r), p.d_lc_min_m);
  s = d_f + 0.6 * d_r;
  if rel_r > 0.3
    ttc = d_r / max(rel_r, 0.05);
    s = s - max(0.0, 8.0 - ttc) * 2.0;
  end
end

function v = field_or(s, name, default)
  v = default;
  if isstruct(s) && isfield(s, name)
    v = s.(name);
  end
end
