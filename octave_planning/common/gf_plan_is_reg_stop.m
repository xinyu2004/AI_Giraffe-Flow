% Regulatory must-stop row (light / stop-ahead). Not a physical object class.
function yes = gf_plan_is_reg_stop(cls)
  p = gf_plan_cal();
  yes = double(cls == p.cls_reg_stop);
end
