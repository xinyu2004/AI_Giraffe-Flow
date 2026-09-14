% m_park_tick — parking APA path (stage P): slot polyline clipped by FreespaceNear.
% Gold intent: confirmed free slot → approach polyline; stop before FS hard edge.
% C 1:1: gf_octave_planning::m_park_tick / oct_gen::m_park_tick
%
% Inputs (ego frame):
%   slot_*, free, confirmed, optional d_occ_m[36] (empty = no clip)
% Outputs:
%   valid, n, x[], y[], yaw[]

function out = m_park_tick(slot_x, slot_y, slot_yaw, slot_len, slot_wid, free, confirmed, d_occ_m)
  if nargin < 8
    d_occ_m = [];
  end
  out.valid = 0;
  out.n = 0;
  out.x = zeros(1, 32);
  out.y = zeros(1, 32);
  out.yaw = zeros(1, 32);
  if ~confirmed || ~free
    return;
  end
  n = 16;
  margin = 0.6;
  kept = 0;
  for i = 1:n
    a = (i - 1) / max(n - 1, 1);
    x = a * slot_x;
    y = a * slot_y;
    yaw = a * slot_yaw;
    if ~isempty(d_occ_m)
      r = hypot(x, y);
      if r >= 0.2
        ang = atan2(y, x);
        if ang < 0
          ang = ang + 2 * pi;
        end
        sec = floor(ang / (2 * pi) * 36);
        sec = mod(sec, 36) + 1;
        if r + margin > d_occ_m(sec)
          break;
        end
      end
    end
    kept = kept + 1;
    out.x(kept) = x;
    out.y(kept) = y;
    out.yaw(kept) = yaw;
  end
  if kept < 2
    return;
  end
  out.n = kept;
  out.valid = 1;
  out.slot_len = slot_len;
  out.slot_wid = slot_wid;
end
