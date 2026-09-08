% Stop-line station [m] from DSTSR red/yellow. None / light gone → d_cal_cap.
% TSR present means the light is known — do not hide it behind a lead's D_see.
% s_line <= 0 while the light is still packed: hold at the line (do not release).
function s_stop = gf_plan_reg_stop(obj, c0)
  p = gf_plan_cal();
  if nargin < 2 || isempty(c0)
    c0 = 0.0;
  end
  s_stop = p.d_cal_cap_m;
  [n, d, ~, lat, ~, cls] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  hold = max(p.reg_stop_hold_m, 0.2);
  behind = max(p.reg_stop_behind_m, 0.0);
  for k = 1:n
    if gf_plan_is_reg_stop(cls(k)) < 0.5
      continue;
    end
    if abs(lat(k) - c0) > p.reg_stop_lat_m
      continue;
    end
    if d(k) < -behind || d(k) > p.lon_max_d_m
      continue;
    end
    s_line = d(k) - p.reg_stop_margin_m;
    if s_line <= 0.0
      if hold < s_stop
        s_stop = hold;
      end
    elseif s_line < s_stop
      s_stop = s_line;
    end
  end
end
