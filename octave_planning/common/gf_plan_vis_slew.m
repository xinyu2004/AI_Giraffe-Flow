% Fall immediately, rise by alpha (per tick). Used by horizon hysteresis.
function y = gf_plan_vis_slew(raw, prev, alpha)
  if prev <= 0.0
    y = raw;
    return;
  end
  if raw < prev
    y = raw;
  else
    y = prev + alpha * (raw - prev);
  end
end
