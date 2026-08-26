% Piecewise v along path x. Same obj matrix as v_at_s.
function v_s = gf_plan_speed_profile(x_m, v_ego, obj, D_see, lane_ok)
  n = length(x_m);
  v_s = zeros(1, n);
  for i = 1:n
    v_s(i) = gf_plan_v_at_s(x_m(i), v_ego, obj, D_see, lane_ok);
  end
end
