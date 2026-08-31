% Optical see along host poly (ego +x). Bearing |atan2(y,x)| vs driving wedge.
% Not road-tangent heading (that was D_bend). Not an FCM field.
function D_fov = gf_plan_d_fov(c0, c1, c2, c3, x_end)
  p = gf_plan_cal();
  if nargin < 1 || isempty(c0)
    c0 = 0.0;
  end
  if nargin < 2 || isempty(c1)
    c1 = 0.0;
  end
  if nargin < 3 || isempty(c2)
    c2 = 0.0;
  end
  if nargin < 4 || isempty(c3)
    c3 = 0.0;
  end
  D_fov = p.d_cal_cap_m;
  if nargin >= 5 && ~isempty(x_end) && x_end > 0.5
    D_fov = min(D_fov, x_end);
  end
  half = 0.5 * p.see_fov_deg * pi / 180.0;
  step = 2.0;
  x = 2.0;
  while x <= D_fov + 1e-6
    y = c0 + c1 * x + c2 * x * x + c3 * x * x * x;
    if abs(atan2(y, x)) > half
      D_fov = x;
      return;
    end
    x = x + step;
  end
end
