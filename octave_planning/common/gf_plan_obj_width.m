% Class default width (EU cal). Pack has no width column yet.
function w = gf_plan_obj_width(cls, is_ped)
  p = gf_plan_cal();
  w = p.obj_width_car_m;
  if nargin >= 2 && is_ped ~= 0
    w = p.obj_width_ped_m;
    return;
  end
  if cls == p.cls_truck
    w = p.obj_width_truck_m;
  elseif cls == p.cls_ped
    w = p.obj_width_ped_m;
  end
end
