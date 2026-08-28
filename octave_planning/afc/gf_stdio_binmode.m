% Windows: call DLD that _setmode(stdin/stdout, _O_BINARY) in THIS Octave process.
% Parent exec+setmode does not transfer CRT mode (Windows spawn). Do not printf stdout (IPC).

function gf_stdio_binmode()
  if ~ispc()
    return;
  end
  persistent done;
  if ~isempty(done) && done
    return;
  end
  try
    gf_stdio_binmode_oct();
    done = true;
  catch
    fputs(stderr, ['m_plan_stdio: gf_stdio_binmode_oct missing or failed. ' ...
                   'Bridge should mkoctfile afc/gf_stdio_binmode_oct.cc once.\n']);
    fflush(stderr);
  end
end
