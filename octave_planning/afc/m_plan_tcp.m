% Disabled on Windows auto: Octave JVM + java.net.Socket segfaults (seen on CARLA Host).
% Opt-in only: GF_OCTAVE_IPC=tcp

function m_plan_tcp(port)
  more off;
  page_screen_output(0);
  warning('off', 'all');
  if exist('usejava', 'file') ~= 2 || ~usejava('jvm')
    error('m_plan_tcp: Octave JVM required');
  end
  sock = javaObject('java.net.Socket', '127.0.0.1', int32(port));
  sock.setTcpNoDelay(true);
  br = javaObject('java.io.BufferedReader', ...
                  javaObject('java.io.InputStreamReader', sock.getInputStream(), 'US-ASCII'));
  bw = javaObject('java.io.BufferedWriter', ...
                  javaObject('java.io.OutputStreamWriter', sock.getOutputStream(), 'US-ASCII'));
  while true
    line = br.readLine();
    if isempty(line)
      break;
    end
    in = sscanf(char(line), '%f');
    vec = m_plan_tick_pack(in);
    bw.write(sprintf('%.9g ', vec));
    bw.write(sprintf('\n'));
    bw.flush();
  end
end
