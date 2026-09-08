% 1 = blocks host lane, 0 = in-lane gap enough to pass. No LC.
% Cut-in: near the host band AND closing (rel). Pulling-away neighbour is not a cut-in.
function w = gf_plan_obj_weight(lat, heading, is_ped, len_m, cls, c0, rel)
  p = gf_plan_cal();
  if nargin < 4 || isempty(len_m)
    len_m = 4.5;
  end
  if nargin < 5 || isempty(cls)
    cls = 1.0;
  end
  if nargin < 6 || isempty(c0)
    c0 = 0.0;
  end
  if nargin < 7 || isempty(rel)
    rel = 0.0;
  end
  if gf_plan_is_reg_stop(cls) > 0.5
    w = 0.0;
    return;
  end
  occupy = gf_plan_lane_occupy(c0, lat, len_m, cls, heading, is_ped);
  if gf_plan_can_pass(occupy, cls, is_ped) > 0.5
    w = 0.0;
  else
    w = 1.0;
  end
  wo = gf_plan_obj_width(cls, is_ped);
  half = 0.5 * (wo * abs(cos(heading)) + max(len_m, 0.5) * abs(sin(heading)));
  gap = (abs(lat - c0) - half) - 0.5 * p.lane_width_m;
  closing = rel < -p.cutin_close_mps;
  if gap < p.cutin_approach_m && lat * heading < -0.02 && closing
    w = min(1.0, max(w, 0.55) + p.cutin_head_gain * min(abs(heading), 0.5));
  end
end
