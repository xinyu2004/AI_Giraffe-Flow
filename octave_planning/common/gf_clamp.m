% Shared whitelist helpers (no plot/I/O/eval).
function y = gf_clamp(x, lo, hi)
  y = min(max(x, lo), hi);
end
