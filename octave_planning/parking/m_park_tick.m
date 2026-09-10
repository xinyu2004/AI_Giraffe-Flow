% m_park_tick — parking APA path stub (stage P).
% Gold intent: confirmed slot → simple reverse/in-slot polyline (A* later).
% C 1:1: gf_octave_planning::m_park_tick / oct_gen::m_park_tick
%
% Inputs (ego frame):
%   slot_x, slot_y, slot_yaw, slot_len, slot_wid, free, confirmed
% Outputs:
%   valid, n, x[], y[], yaw[]

function out = m_park_tick(slot_x, slot_y, slot_yaw, slot_len, slot_wid, free, confirmed)
  out.valid = 0;
  out.n = 0;
  out.x = zeros(1, 32);
  out.y = zeros(1, 32);
  out.yaw = zeros(1, 32);
  if ~confirmed || ~free
    return;
  end
  % Straight approach then lateral into slot center (geometric stub, not A*).
  n = 16;
  for i = 1:n
    a = (i - 1) / max(n - 1, 1);
    out.x(i) = a * slot_x;
    out.y(i) = a * slot_y;
    out.yaw(i) = a * slot_yaw;
  end
  out.n = n;
  out.valid = 1;
  out.slot_len = slot_len;
  out.slot_wid = slot_wid;
end
