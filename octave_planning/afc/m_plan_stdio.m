% Host IPC: blocking binary stdio (anonymous pipe from Python).
% Windows: gf_stdio_binmode() must run in-process before fread (CRT text mode).
% Protocol LE: uint32 magic 0x47504C4E, uint32 n, n float64. Same for reply.

function m_plan_stdio()
  more off;
  page_screen_output(0);
  warning('off', 'all');
  gf_stdio_binmode();
  magic = uint32(hex2dec('47504C4E'));
  while true
    hdr = fread_n(stdin, 2, 'uint32');
    if numel(hdr) < 2
      break;
    end
    if hdr(1) ~= magic
      error('m_plan_stdio: bad magic');
    end
    n = double(hdr(2));
    if n < 1 || n > 4096
      error('m_plan_stdio: bad n');
    end
    in = fread_n(stdin, n, 'double');
    if numel(in) < n
      break;
    end
    vec = m_plan_tick_pack(in);
    fwrite(stdout, [magic, uint32(numel(vec))], 'uint32');
    fwrite(stdout, vec(:), 'double');
    fflush(stdout);
  end
end

function x = fread_n(fid, n, prec)
  x = [];
  while numel(x) < n
    c = fread(fid, n - numel(x), prec);
    if isempty(c)
      return;
    end
    x = [x; c(:)];
  end
end
