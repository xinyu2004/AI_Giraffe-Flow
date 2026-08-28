#include <octave/oct.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

DEFUN_DLD (gf_stdio_binmode_oct, args, nargout,
           "Set stdin/stdout to CRT binary mode (Windows). Call from m_plan_stdio.")
{
  (void) args;
  (void) nargout;
#ifdef _WIN32
  (void) _setmode (_fileno (stdin), _O_BINARY);
  (void) _setmode (_fileno (stdout), _O_BINARY);
#endif
  return octave_value_list ();
}
