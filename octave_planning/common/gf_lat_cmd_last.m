% Shared actuator command (rad). Follow and LKA rate-limit from the same last.
% Not a second controller. 1:1 lat_follow.hpp lat_cmd_last.

function s = gf_lat_cmd_last(setv)
  persistent last
  if isempty(last)
    last = 0.0;
  end
  if nargin >= 1 && ~isempty(setv)
    last = setv;
  end
  s = last;
end
