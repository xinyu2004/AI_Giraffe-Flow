% Piecewise v along path x. s_stop from gf_plan_reg_stop (once per tick).
function v_s = gf_plan_speed_profile(x_m, v_ego, obj, D_see, lane_ok, c0, s_stop, ...
                                     v_sign_max, v_sign_min)
  if nargin < 6 || isempty(c0)
    c0 = 0.0;
  end
  if nargin < 7 || isempty(s_stop)
    s_stop = gf_plan_reg_stop(obj, c0);
  end
  if nargin < 8 || isempty(v_sign_max)
    v_sign_max = 1.0e6;
  end
  if nargin < 9 || isempty(v_sign_min)
    v_sign_min = 0.0;
  end
  n = length(x_m);
  v_s = zeros(1, n);
  for i = 1:n
    v_s(i) = gf_plan_v_at_s(x_m(i), v_ego, obj, D_see, lane_ok, c0, s_stop, ...
                            v_sign_max, v_sign_min);
  end
end
