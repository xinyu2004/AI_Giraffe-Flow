% LC road pose. Planning state, not a steer law.
% Paint is the map when geom is there. DR increment only while paint is gone.
% Pre-remap: y = -e_y (old host center at 0). Post: y = W - e_y (target is host).
% 1:1 lc_pose.hpp.

function pose = gf_lc_pose(pose, e_y, c1, paint_ok, W, y_dr, psi_dr)
  p = gf_plan_cal();
  if nargin < 1 || isempty(pose)
    pose = gf_lc_pose_zero();
  end
  if nargin < 2 || isempty(e_y)
    e_y = 0.0;
  end
  if nargin < 3 || isempty(c1)
    c1 = 0.0;
  end
  if nargin < 4 || isempty(paint_ok)
    paint_ok = 0.0;
  end
  if nargin < 5 || isempty(W)
    W = 0.0;
  end
  if nargin < 6 || isempty(y_dr)
    y_dr = 0.0;
  end
  if nargin < 7 || isempty(psi_dr)
    psi_dr = 0.0;
  end

  y_pre = -e_y;
  y_post = W - e_y;
  if paint_ok > 0.5
    if pose.remapped < 0.5 && pose.have > 0.5
      closer_post = abs(y_post - pose.y) + 0.40 < abs(y_pre - pose.y);
      jumped = abs(e_y - pose.e_y) > p.lc_remap_ey_m;
      if closer_post || jumped
        pose.remapped = 1;
      end
    end
    if pose.remapped > 0.5
      pose.y = y_post;
    else
      pose.y = y_pre;
    end
    pose.psi = -c1;
    pose.e_y = e_y;
  else
    if pose.have > 0.5
      pose.y = pose.y + (y_dr - pose.y_dr);
      pose.psi = pose.psi + (psi_dr - pose.psi_dr);
    else
      pose.y = y_dr;
      pose.psi = psi_dr;
    end
  end
  pose.y_dr = y_dr;
  pose.psi_dr = psi_dr;
  pose.have = 1;
  pose.paint_ok = paint_ok > 0.5;
end

function z = gf_lc_pose_zero()
  z.have = 0;
  z.remapped = 0;
  z.paint_ok = 0;
  z.y = 0.0;
  z.psi = 0.0;
  z.e_y = 0.0;
  z.y_dr = 0.0;
  z.psi_dr = 0.0;
end
