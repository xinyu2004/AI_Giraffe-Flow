% Host IPC: blocking named pipe / FIFO. Same binary frame as m_plan_stdio.
% Windows: //./pipe/<name>  (Win32 named pipe, no JVM, no pause/file poll)
% Linux:   fifo path        (GF_OCTAVE_IPC=pipe; auto stays stdio)
% Protocol LE: uint32 magic 0x47504C4E, uint32 n, n float64. Same for reply.

function m_plan_pipe(in_path, out_path)
  more off;
  page_screen_output(0);
  warning('off', 'all');
  if nargin < 2
    error('m_plan_pipe: need in_path, out_path');
  end
  magic = uint32(hex2dec('47504C4E'));
  fin = fopen(in_path, 'rb');
  if fin < 0
    error('m_plan_pipe: fopen in failed: %s', in_path);
  end
  fout = fopen(out_path, 'wb');
  if fout < 0
    fclose(fin);
    error('m_plan_pipe: fopen out failed: %s', out_path);
  end
  while true
    hdr = fread_n(fin, 2, 'uint32');
    if numel(hdr) < 2
      break;
    end
    if hdr(1) ~= magic
      error('m_plan_pipe: bad magic');
    end
    n = double(hdr(2));
    if n < 1 || n > 4096
      error('m_plan_pipe: bad n');
    end
    in = fread_n(fin, n, 'double');
    if numel(in) < n
      break;
    end
    vec = m_plan_tick_pack(in);
    fwrite(fout, [magic, uint32(numel(vec))], 'uint32');
    fwrite(fout, vec(:), 'double');
    fflush(fout);
  end
  fclose(fin);
  fclose(fout);
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
