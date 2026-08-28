% Host IPC: two seq files (each side writes only its own). No JVM, no replace().
% Windows: ctl.bin replace() hits ERROR_ACCESS_DENIED if Octave still has it open.

function m_plan_fileloop(io_dir)
  more off;
  page_screen_output(0);
  warning('off', 'all');
  in_bin = [io_dir '/in.bin'];
  out_bin = [io_dir '/out.bin'];
  in_seq_p = [io_dir '/in_seq.bin'];
  out_seq_p = [io_dir '/out_seq.bin'];
  last = uint64(0);
  write_u64(out_seq_p, uint64(0));
  while true
    n = wait_u64(in_seq_p, last);
    fid = fopen(in_bin, 'rb');
    if fid < 0
      continue;
    end
    in = fread(fid, inf, 'double');
    fclose(fid);
    vec = m_plan_tick_pack(in);
    fid = fopen(out_bin, 'wb');
    if fid >= 0
      fwrite(fid, vec(:), 'double');
      fclose(fid);
    end
    last = n;
    write_u64(out_seq_p, last);
  end
end

function n = wait_u64(p, last)
  tries = 0;
  while true
    n = read_u64(p);
    if n > last
      return
    end
    tries = tries + 1;
    if tries > 80
      pause(0.001);
      tries = 0;
    end
  end
end

function n = read_u64(p)
  n = uint64(0);
  fid = fopen(p, 'rb');
  if fid < 0
    return
  end
  raw = fread(fid, 1, 'uint64');
  fclose(fid);
  if ~isempty(raw)
    n = uint64(raw(1));
  end
end

function write_u64(p, n)
  fid = fopen(p, 'wb');
  if fid < 0
    return
  end
  fwrite(fid, uint64(n), 'uint64');
  fclose(fid);
end
