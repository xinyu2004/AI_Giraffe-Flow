% Host FFI shim — same algorithm as m_plan_tick, one numeric vector in/out.
% oct2py struct+char is ~200ms; a double row is cheap. Do not generate this to C.

function vec = m_plan_tick_pack(in)
  in = double(in(:))';
  if numel(in) < 14
    error('m_plan_tick_pack: short input');
  end
  v = in(1);
  steer_deg = in(2);
  lane_valid = in(3);
  e_y = in(4);
  c0 = in(5);
  c1 = in(6);
  c2 = in(7);
  c3 = in(8);
  x_end = in(9);
  lane_conf = in(10);
  lane_count = in(11);
  D_see_prev = in(12);
  T_plan_prev = in(13);
  nobj = max(0, min(8, round(in(14))));
  obj = [];
  need = 14 + nobj * 7;
  if nobj > 0 && numel(in) >= need
    obj = reshape(in(15:14 + nobj * 7), 7, nobj)';
  end

  out = m_plan_tick(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, ...
                    lane_conf, lane_count, obj, D_see_prev, T_plan_prev);

  mid = 0.0;
  if ischar(out.mode) || isstring(out.mode)
    s = char(out.mode);
    if strcmp(s, 'acc')
      mid = 1.0;
    elseif strcmp(s, 'aeb')
      mid = 2.0;
    elseif strcmp(s, 'pullaway')
      mid = 3.0;
    end
  else
    mid = double(out.mode);
  end

  n = 16;
  x = zeros(1, n);
  y = zeros(1, n);
  vv = zeros(1, n);
  xa = out.x_m(:)';
  ya = out.y_m(:)';
  va = out.v_mps(:)';
  k = min([n, numel(xa), numel(ya), numel(va)]);
  if k > 0
    x(1:k) = xa(1:k);
    y(1:k) = ya(1:k);
    vv(1:k) = va(1:k);
  end

  hdr = [out.throttle, out.brake, out.steer, out.target_speed_mps, ...
         out.D_see, out.T_plan, out.D_occ, out.a_req, out.horizon_m, ...
         out.allow_lc, mid, out.t_m_s, k, 0.0];
  vec = [hdr, x, y, vv];
end
