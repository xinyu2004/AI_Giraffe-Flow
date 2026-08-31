% In-lane squeeze only (no LC). free = W - occupy >= ego + side clear.
% Pedestrian with any lane overlap: cannot pass.
function ok = gf_plan_can_pass(occupy, cls, is_ped)
  p = gf_plan_cal();
  if nargin < 3
    is_ped = 0.0;
  end
  if (is_ped ~= 0 || cls == p.cls_ped) && occupy > 1.0e-3
    ok = 0.0;
    return;
  end
  free = p.lane_width_m - occupy;
  ok = double(free >= (p.ego_width_m + p.pass_clear_m));
end
