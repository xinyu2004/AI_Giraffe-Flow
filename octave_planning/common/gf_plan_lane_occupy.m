% How much of the host lane (width W, center c0) the object covers on y.
% Heading rotates the box: lateral span = w|cos| + len|sin|. Not a pass license.
function occupy = gf_plan_lane_occupy(c0, lat, len_m, cls, heading, is_ped)
  p = gf_plan_cal();
  if nargin < 6
    is_ped = 0.0;
  end
  W = p.lane_width_m;
  wo = gf_plan_obj_width(cls, is_ped);
  half = 0.5 * (wo * abs(cos(heading)) + max(len_m, 0.5) * abs(sin(heading)));
  y0 = c0 - 0.5 * W;
  y1 = c0 + 0.5 * W;
  o0 = lat - half;
  o1 = lat + half;
  occupy = max(0.0, min(y1, o1) - max(y0, o0));
end
