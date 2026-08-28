"""Host planning: Octave .m only. Hot path is octave-cli pipe/stdio/file, not oct2py."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .semantic_map import (
    CTRL_MODE_NAMES,
    PlanningResult,
    PlanningView,
    lane_code_from_path,
)

_SESSION: Any = None
_LAST_PLAN_LOG = 0.0
_D_SEE_PREV = 0.0
_T_PLAN_PREV = 0.0
_LAST_PLAN_WALL_S = 0.0
_LAST_PLAN_M_S = 0.0
_LAST_PLAN_FFI_S = 0.0

# m_plan_tick_pack layout (Host FFI). Keep in sync with afc/m_plan_tick_pack.m
_IN_HDR = 14
_OBJ_N_MAX = 8
_OBJ_W = 7
_IN_N = _IN_HDR + _OBJ_N_MAX * _OBJ_W
_OUT_HDR = 14
_TRAJ_N = 16
_OUT_N = _OUT_HDR + _TRAJ_N * 3
_STDIO_MAGIC = 0x47504C4E
_LAST_IPC = "none"
_KNOWN_IPC = ("pipe", "stdio", "file", "oct2py", "tcp")
_PIPE_BUF = 65536
_ERROR_PIPE_CONNECTED = 535
_ERROR_BROKEN_PIPE = 109
_PIPE_ACCESS_INBOUND = 0x00000001
_PIPE_ACCESS_OUTBOUND = 0x00000002
_FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
_PIPE_TYPE_BYTE = 0x00000000
_PIPE_READMODE_BYTE = 0x00000000
_PIPE_WAIT = 0x00000000
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_K32: Any = None

# log-only, match gf_plan_cal (avoid oct2py cal struct)
_LAT_EY_INVALID_M = 3.0
_LAT_C1_INVALID = 0.40
_LAT_EY_SLOW_M = 1.0


def resolve_octave_planning() -> Optional[Path]:
    """Directory that contains ``afc/m_lon_acc_aeb.m``."""
    env = (os.environ.get("GF_OCTAVE_PLANNING") or "").strip().strip('"').strip("'")
    here = Path(__file__).resolve()
    scenarios = here.parents[1]
    candidates: list[Path] = []
    if env:
        p = Path(env).expanduser()
        p = p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
        candidates.append(p)
        if (p / "octave_planning").is_dir():
            candidates.append(p / "octave_planning")
    candidates.extend(
        [
            here.parents[2] / "octave_planning",
            scenarios.parent / "octave_planning",
            scenarios / "octave_planning",
        ]
    )
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if (cand / "afc" / "m_lon_acc_aeb.m").is_file():
            return cand
    return None


def last_plan_timing() -> tuple[float, float, float]:
    """Return (wall_s, m_s, ffi_s) for the last ``plan_tick``."""
    return _LAST_PLAN_WALL_S, _LAST_PLAN_M_S, _LAST_PLAN_FFI_S


def last_ipc() -> str:
    return _LAST_IPC


def ipc_order(want: str, platform: str) -> list[str]:
    """auto: stdio then file on both OS. Windows named-pipe fopen does not work.

    Windows stdio needs in-process _setmode (gf_stdio_binmode_oct). Never default tcp.
    """
    w = (want or "auto").strip().lower()
    if w in _KNOWN_IPC:
        return [w]
    return ["stdio", "file"]


_HDR_ST = struct.Struct("<II")
_ST_CACHE: dict[int, struct.Struct] = {}


def _dbl_st(n: int) -> struct.Struct:
    st = _ST_CACHE.get(n)
    if st is None:
        st = struct.Struct(f"<{n}d")
        _ST_CACHE[n] = st
    return st


def pack_stdio_frame(vec: list[float]) -> bytes:
    n = len(vec)
    return _HDR_ST.pack(_STDIO_MAGIC, n) + _dbl_st(n).pack(*vec)


def unpack_stdio_frame(buf: bytes) -> list[float]:
    if len(buf) < 8:
        raise ValueError("stdio frame short hdr")
    magic, n = _HDR_ST.unpack_from(buf, 0)
    if magic != _STDIO_MAGIC or n < 1 or n > 4096:
        raise ValueError(f"stdio bad hdr magic={magic:#x} n={n}")
    need = 8 + 8 * n
    if len(buf) < need:
        raise ValueError("stdio frame short body")
    return list(_dbl_st(n).unpack_from(buf, 8))


def _in_arg(vec: list[float]) -> Any:
    try:
        import numpy as np  # type: ignore

        return np.asarray(vec, dtype=np.float64)
    except ImportError:
        return vec


def plan_log_enabled() -> bool:
    v = (os.environ.get("GF_OCTAVE_PLAN_LOG") or "").strip().lower()
    return v in ("1", "on", "true", "yes")


def _octave_addpath(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/")


def _b01(v: bool) -> float:
    return 1.0 if v else 0.0


def _as_vec(x: Any) -> list[float]:
    if x is None:
        return []
    if hasattr(x, "flatten"):
        return [float(v) for v in list(x.flatten())]
    if isinstance(x, (list, tuple)):
        out: list[float] = []
        for v in x:
            if isinstance(v, (list, tuple)):
                out.extend(float(u) for u in v)
            else:
                out.append(float(v))
        return out
    return [float(x)]


def _as_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(x[0])


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    s = str(x).strip()
    return s.strip("'\"")


def _find_octave() -> str:
    env = (os.environ.get("GF_OCTAVE") or os.environ.get("OCTAVE") or "").strip()
    if env:
        return env
    for name in ("octave-cli", "octave-cli.exe", "octave", "octave.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        "octave-cli not in PATH. Set GF_OCTAVE=C:/path/octave-cli.exe"
    )


def _find_mkoctfile() -> Optional[str]:
    env = (os.environ.get("GF_MKOCTFILE") or "").strip()
    if env:
        return env
    for name in ("mkoctfile", "mkoctfile.exe"):
        found = shutil.which(name)
        if found:
            return found
    try:
        oct_bin = Path(_find_octave()).resolve().parent
    except FileNotFoundError:
        return None
    names = ("mkoctfile.exe", "mkoctfile")
    cands: list[Path] = []
    cur: Path | None = oct_bin
    for _ in range(5):
        if cur is None:
            break
        for name in names:
            cands.append(cur / name)
            cands.append(cur / "mingw64" / "bin" / name)
            cands.append(cur / "clang64" / "bin" / name)
        cur = cur.parent if cur.parent != cur else None
    seen: set[Path] = set()
    for cand in cands:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file():
            return str(cand)
    return None


def _ensure_win_stdio_oct(root: Path) -> None:
    """Compile gf_stdio_binmode_oct.oct in a separate process (never on IPC stdout)."""
    if sys.platform != "win32":
        return
    src = root / "afc" / "gf_stdio_binmode_oct.cc"
    out = root / "afc" / "gf_stdio_binmode_oct.oct"
    if not src.is_file():
        print(f"[octave_bridge] missing {src}", flush=True)
        return
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime:
        return
    mk = _find_mkoctfile()
    if mk is None:
        print(
            "[octave_bridge] mkoctfile not found; Windows stdio may stay text-mode. "
            "Install Octave mkoctfile or set GF_MKOCTFILE.",
            flush=True,
        )
        return
    env = os.environ.copy()
    bindir = str(Path(mk).resolve().parent)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    print(f"[octave_bridge] mkoctfile {src.name} via {mk}", flush=True)
    r = subprocess.run(
        [mk, "-o", str(out), str(src)],
        cwd=str(src.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        print(f"[octave_bridge] mkoctfile failed: {err}", flush=True)
        return
    print(f"[octave_bridge] wrote {out}", flush=True)


def _win_setmode_stdio_pipes(proc: subprocess.Popen[bytes]) -> None:
    if sys.platform != "win32":
        return
    import msvcrt

    for stream in (proc.stdin, proc.stdout):
        if stream is None:
            continue
        try:
            msvcrt.setmode(stream.fileno(), os.O_BINARY)
        except Exception as exc:  # noqa: BLE001
            print(f"[octave_bridge] setmode pipe: {exc}", flush=True)


def _octave_cmd(root: Path, eval_stmt: str) -> list[str]:
    common = _octave_addpath(root / "common")
    afc = _octave_addpath(root / "afc")
    stmt = f"addpath('{common}');addpath('{afc}');{eval_stmt}"
    return [_find_octave(), "-qf", "--eval", stmt]


def _drain_stderr(proc: subprocess.Popen[bytes]) -> None:
    err = proc.stderr
    if err is None:
        return
    try:
        while True:
            line = err.readline()
            if not line:
                break
            txt = line.decode("utf-8", "replace").rstrip()
            if txt:
                print(f"[octave] {txt}", flush=True)
    except Exception:  # noqa: BLE001
        return


def _dummy_in() -> list[float]:
    vec = [0.0] * _IN_N
    vec[13] = 1.0
    vec[14] = 999.0
    vec[16] = 99.0
    vec[17] = 4.5
    return vec


def _write_bytes_retry(path: Path, data: bytes, *, attempts: int = 25) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            path.write_bytes(data)
            return
        except OSError as exc:
            last = exc
            time.sleep(0.002)
    raise last if last else OSError(f"write failed {path}")


def _read_bytes_retry(path: Path, *, attempts: int = 25) -> bytes:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return path.read_bytes()
        except OSError as exc:
            last = exc
            time.sleep(0.002)
    raise last if last else OSError(f"read failed {path}")


def _write_u64(path: Path, n: int) -> None:
    _write_bytes_retry(path, struct.pack("<Q", int(n) & 0xFFFFFFFFFFFFFFFF))


def _read_u64(path: Path) -> int:
    try:
        raw = _read_bytes_retry(path)
    except OSError:
        return 0
    if len(raw) < 8:
        return 0
    return int(struct.unpack_from("<Q", raw, 0)[0])


def _win_k32() -> Any:
    global _K32
    if _K32 is not None:
        return _K32
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateNamedPipeW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    k.CreateNamedPipeW.restype = ctypes.c_void_p
    k.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k.ConnectNamedPipe.restype = ctypes.c_int
    k.ReadFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    k.ReadFile.restype = ctypes.c_int
    k.WriteFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    k.WriteFile.restype = ctypes.c_int
    k.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    k.FlushFileBuffers.restype = ctypes.c_int
    k.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
    k.DisconnectNamedPipe.restype = ctypes.c_int
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.CloseHandle.restype = ctypes.c_int
    _K32 = k
    return k


def _win_bad_handle(h: Any) -> bool:
    try:
        v = int(h)
    except (TypeError, ValueError):
        return True
    return v in (0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)


class _WinPipeStream:
    """Binary stream over a Win32 named-pipe server handle (byte mode)."""

    def __init__(self, handle: Any, name: str) -> None:
        self.h = handle
        self.name = name

    def read(self, n: int) -> bytes:
        if n <= 0 or self.h is None:
            return b""
        k = _win_k32()
        buf = (ctypes.c_char * n)()
        got = ctypes.c_uint32(0)
        ok = k.ReadFile(self.h, buf, n, ctypes.byref(got), None)
        if not ok:
            err = ctypes.get_last_error()
            if err in (_ERROR_BROKEN_PIPE, 233):
                return b""
            raise OSError(err, f"ReadFile {self.name} err={err}")
        return bytes(buf[: int(got.value)])

    def write(self, data: bytes) -> int:
        if not data:
            return 0
        if self.h is None:
            raise RuntimeError(f"pipe closed {self.name}")
        k = _win_k32()
        off = 0
        while off < len(data):
            chunk = data[off:]
            buf = (ctypes.c_char * len(chunk)).from_buffer_copy(chunk)
            got = ctypes.c_uint32(0)
            ok = k.WriteFile(self.h, buf, len(chunk), ctypes.byref(got), None)
            if not ok:
                err = ctypes.get_last_error()
                raise OSError(err, f"WriteFile {self.name} err={err}")
            if int(got.value) <= 0:
                raise OSError(f"WriteFile {self.name} wrote 0")
            off += int(got.value)
        return len(data)

    def flush(self) -> None:
        if self.h is None:
            return
        _win_k32().FlushFileBuffers(self.h)

    def close(self) -> None:
        h = self.h
        self.h = None
        if h is None or _win_bad_handle(h):
            return
        k = _win_k32()
        try:
            k.DisconnectNamedPipe(h)
        except Exception:  # noqa: BLE001
            pass
        k.CloseHandle(h)


def _win_create_pipe(api_name: str, outbound: bool) -> Any:
    k = _win_k32()
    access = _PIPE_ACCESS_OUTBOUND if outbound else _PIPE_ACCESS_INBOUND
    mode = (
        _PIPE_TYPE_BYTE
        | _PIPE_READMODE_BYTE
        | _PIPE_WAIT
        | _PIPE_REJECT_REMOTE_CLIENTS
    )
    h = k.CreateNamedPipeW(
        api_name,
        access | _FILE_FLAG_FIRST_PIPE_INSTANCE,
        mode,
        1,
        _PIPE_BUF,
        _PIPE_BUF,
        5000,
        None,
    )
    if _win_bad_handle(h):
        err = ctypes.get_last_error()
        raise OSError(err, f"CreateNamedPipeW {api_name} err={err}")
    return h


def _win_connect_pipe(h: Any, name: str, timeout_s: float) -> None:
    box: list[Any] = []

    def _run() -> None:
        ok = _win_k32().ConnectNamedPipe(h, None)
        err = ctypes.get_last_error()
        if ok or err == _ERROR_PIPE_CONNECTED:
            box.append(True)
            return
        box.append(OSError(err, f"ConnectNamedPipe {name} err={err}"))

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise TimeoutError(f"named pipe connect timeout {name}")
    if not box:
        raise TimeoutError(f"named pipe connect timeout {name}")
    if box[0] is not True:
        raise box[0]


def _fifo_open_writer(path: Path, timeout_s: float) -> Any:
    deadline = time.monotonic() + timeout_s
    flags = os.O_WRONLY | getattr(os, "O_BINARY", 0)
    while time.monotonic() < deadline:
        try:
            fd = os.open(str(path), flags | os.O_NONBLOCK)
            os.set_blocking(fd, True)
            return os.fdopen(fd, "wb", buffering=0)
        except OSError as exc:
            if exc.errno in (errno.ENXIO, errno.EAGAIN, errno.EWOULDBLOCK):
                time.sleep(0.01)
                continue
            raise
    raise TimeoutError(f"fifo writer open timeout {path}")


def _fifo_open_reader(path: Path, timeout_s: float) -> Any:
    box: list[Any] = []

    def _run() -> None:
        try:
            box.append(open(path, "rb", buffering=0))
        except Exception as exc:  # noqa: BLE001
            box.append(exc)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive() or not box:
        raise TimeoutError(f"fifo reader open timeout {path}")
    if isinstance(box[0], Exception):
        raise box[0]
    return box[0]


class _PipePeer:
    ipc = "pipe"

    def __init__(self, proc: subprocess.Popen[bytes], w: Any, r: Any) -> None:
        self.proc = proc
        self._w = w
        self._r = r
        self._lock = threading.Lock()

    def tick(self, vec: list[float]) -> list[float]:
        if self.proc.poll() is not None:
            raise RuntimeError("octave pipe exited")
        frame = pack_stdio_frame(vec)
        with self._lock:
            self._w.write(frame)
            self._w.flush()
            hdr = _read_exact(self._r, 8)
            magic, n = struct.unpack("<II", hdr)
            if magic != _STDIO_MAGIC or n < 1 or n > 4096:
                raise RuntimeError(f"octave pipe bad hdr {magic:#x} n={n}")
            body = _read_exact(self._r, 8 * n)
        return list(struct.unpack(f"<{n}d", body))

    def close(self) -> None:
        for s in (self._w, self._r):
            try:
                if s is not None:
                    s.close()
            except Exception:  # noqa: BLE001
                pass
        self._w = None
        self._r = None
        try:
            self.proc.kill()
        except Exception:  # noqa: BLE001
            pass


class _TcpPeer:
    ipc = "tcp"

    def __init__(self, proc: subprocess.Popen[bytes], conn: Any, srv: Any) -> None:
        self.proc = proc
        self.conn = conn
        self.srv = srv
        self._lock = threading.Lock()
        self._r = conn.makefile("rb")
        self._w = conn.makefile("wb")

    def tick(self, vec: list[float]) -> list[float]:
        line = (" ".join(f"{x:.9g}" for x in vec) + "\n").encode("ascii")
        with self._lock:
            self._w.write(line)
            self._w.flush()
            raw = self._r.readline()
        if not raw:
            raise RuntimeError("octave tcp eof")
        return [float(x) for x in raw.decode("ascii", "replace").split()]

    def close(self) -> None:
        try:
            self._w.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.srv.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.kill()
        except Exception:  # noqa: BLE001
            pass


class _StdioPeer:
    ipc = "stdio"

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self.proc = proc
        self._lock = threading.Lock()

    def tick(self, vec: list[float]) -> list[float]:
        frame = pack_stdio_frame(vec)
        with self._lock:
            stdin = self.proc.stdin
            stdout = self.proc.stdout
            if stdin is None or stdout is None:
                raise RuntimeError("octave stdio closed")
            stdin.write(frame)
            stdin.flush()
            hdr = _read_exact(stdout, 8)
            magic, n = struct.unpack("<II", hdr)
            if magic != _STDIO_MAGIC or n < 1 or n > 4096:
                raise RuntimeError(f"octave stdio bad hdr {magic:#x} n={n}")
            body = _read_exact(stdout, 8 * n)
        return list(struct.unpack(f"<{n}d", body))

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.kill()
        except Exception:  # noqa: BLE001
            pass


class _FilePeer:
    ipc = "file"

    def __init__(self, proc: subprocess.Popen[bytes], io_dir: Path) -> None:
        self.proc = proc
        self.io_dir = io_dir
        self._lock = threading.Lock()
        self._in_bin = io_dir / "in.bin"
        self._out_bin = io_dir / "out.bin"
        self._in_seq = io_dir / "in_seq.bin"
        self._out_seq = io_dir / "out_seq.bin"
        self._seq = 0
        _write_u64(self._in_seq, 0)
        _write_u64(self._out_seq, 0)

    def tick(self, vec: list[float], *, timeout_s: float = 5.0) -> list[float]:
        payload = struct.pack(f"<{len(vec)}d", *vec)
        with self._lock:
            self._seq += 1
            seq = self._seq
            _write_bytes_retry(self._in_bin, payload)
            _write_u64(self._in_seq, seq)
            deadline = time.monotonic() + timeout_s
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError("octave fileloop timeout")
                if self.proc.poll() is not None:
                    raise RuntimeError("octave fileloop exited")
                got = _read_u64(self._out_seq)
                if got == seq:
                    break
                time.sleep(0.0005)
            raw = _read_bytes_retry(self._out_bin)
        n = len(raw) // 8
        return list(struct.unpack(f"<{n}d", raw[: n * 8]))

    def close(self) -> None:
        try:
            self.proc.kill()
        except Exception:  # noqa: BLE001
            pass
        # io_dir lives under octave_planning/_planio — do not rmtree the tree.


class _Oct2pyPeer:
    ipc = "oct2py"

    def __init__(self, oc: Any) -> None:
        self.oc = oc

    def tick(self, vec: list[float]) -> list[float]:
        return _as_vec(self.oc.m_plan_tick_pack(_in_arg(vec)))

    def close(self) -> None:
        try:
            self.oc.exit()
        except Exception:  # noqa: BLE001
            pass


def _read_exact(stream: Any, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            raise RuntimeError("octave stdio eof")
        buf.extend(chunk)
    return bytes(buf)


def _start_stdio(root: Path) -> _StdioPeer:
    _ensure_win_stdio_oct(root)
    cmd = _octave_cmd(root, "m_plan_stdio();")
    kw: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "bufsize": 0,
    }
    if sys.platform == "win32":
        kw["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = subprocess.Popen(cmd, **kw)
    _win_setmode_stdio_pipes(proc)
    threading.Thread(target=_drain_stderr, args=(proc,), daemon=True).start()
    peer = _StdioPeer(proc)
    _warm_peer(peer, timeout_s=20.0)
    return peer


def _start_tcp(root: Path) -> _TcpPeer:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = int(srv.getsockname()[1])
    cmd = _octave_cmd(root, f"m_plan_tcp({port});")
    kw: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "bufsize": 0,
    }
    if sys.platform == "win32":
        kw["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = subprocess.Popen(cmd, **kw)
    threading.Thread(target=_drain_stderr, args=(proc,), daemon=True).start()
    conn = None
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            srv.close()
            raise RuntimeError("octave tcp exited (JVM missing?)")
        srv.settimeout(0.25)
        try:
            conn, _addr = srv.accept()
            break
        except socket.timeout:
            continue
    if conn is None:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        srv.close()
        raise TimeoutError("octave tcp accept timeout")
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    peer = _TcpPeer(proc, conn, srv)
    peer.tick(_dummy_in())
    return peer


def _start_file(root: Path) -> _FilePeer:
    io_dir = root / "_planio"
    io_dir.mkdir(parents=True, exist_ok=True)
    _write_u64(io_dir / "in_seq.bin", 0)
    _write_u64(io_dir / "out_seq.bin", 0)
    io_q = _octave_addpath(io_dir)
    cmd = _octave_cmd(root, f"m_plan_fileloop('{io_q}');")
    kw: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "bufsize": 0,
    }
    if sys.platform == "win32":
        kw["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = subprocess.Popen(cmd, **kw)
    threading.Thread(target=_drain_stderr, args=(proc,), daemon=True).start()
    peer = _FilePeer(proc, io_dir)
    peer.tick(_dummy_in(), timeout_s=20.0)
    return peer


def _warm_peer(peer: Any, *, timeout_s: float = 20.0) -> None:
    box: list[Any] = []

    def _warm() -> None:
        try:
            box.append(peer.tick(_dummy_in()))
        except Exception as exc:  # noqa: BLE001
            box.append(exc)

    th = threading.Thread(target=_warm, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        peer.close()
        raise TimeoutError(f"octave {getattr(peer, 'ipc', 'ipc')} warm timeout")
    if box and isinstance(box[0], Exception):
        peer.close()
        raise box[0]


def _start_pipe_win32(root: Path) -> _PipePeer:
    token = f"gf_plan_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    in_name = f"{token}_in"
    out_name = f"{token}_out"
    api_in = rf"\\.\pipe\{in_name}"
    api_out = rf"\\.\pipe\{out_name}"
    oct_in = f"//./pipe/{in_name}"
    oct_out = f"//./pipe/{out_name}"
    h_to = None
    h_from = None
    proc: subprocess.Popen[bytes] | None = None
    try:
        h_to = _win_create_pipe(api_in, outbound=True)
        h_from = _win_create_pipe(api_out, outbound=False)
        cmd = _octave_cmd(root, f"m_plan_pipe('{oct_in}','{oct_out}');")
        kw: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "bufsize": 0,
            "creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        }
        proc = subprocess.Popen(cmd, **kw)
        threading.Thread(target=_drain_stderr, args=(proc,), daemon=True).start()
        _win_connect_pipe(h_to, in_name, 15.0)
        _win_connect_pipe(h_from, out_name, 15.0)
        peer = _PipePeer(proc, _WinPipeStream(h_to, in_name), _WinPipeStream(h_from, out_name))
        h_to = None
        h_from = None
        proc = None
        _warm_peer(peer)
        return peer
    except Exception:
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        for h in (h_to, h_from):
            if h is None or _win_bad_handle(h):
                continue
            try:
                _win_k32().CloseHandle(h)
            except Exception:  # noqa: BLE001
                pass
        raise


def _start_pipe_posix(root: Path) -> _PipePeer:
    io_dir = root / "_planio"
    io_dir.mkdir(parents=True, exist_ok=True)
    in_path = io_dir / "to_oct.pipe"
    out_path = io_dir / "from_oct.pipe"
    for p in (in_path, out_path):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        os.mkfifo(p, 0o600)
    oct_in = _octave_addpath(in_path)
    oct_out = _octave_addpath(out_path)
    cmd = _octave_cmd(root, f"m_plan_pipe('{oct_in}','{oct_out}');")
    kw: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "bufsize": 0,
    }
    proc = subprocess.Popen(cmd, **kw)
    threading.Thread(target=_drain_stderr, args=(proc,), daemon=True).start()
    w = None
    r = None
    try:
        w = _fifo_open_writer(in_path, 15.0)
        r = _fifo_open_reader(out_path, 15.0)
        peer = _PipePeer(proc, w, r)
        _warm_peer(peer)
        return peer
    except Exception:
        for s in (w, r):
            try:
                if s is not None:
                    s.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        raise


def _start_pipe(root: Path) -> _PipePeer:
    if sys.platform == "win32":
        return _start_pipe_win32(root)
    return _start_pipe_posix(root)


def _start_oct2py(root: Path) -> _Oct2pyPeer:
    import oct2py  # type: ignore

    oc = oct2py.Oct2Py()
    oc.addpath(_octave_addpath(root / "common"))
    oc.addpath(_octave_addpath(root / "afc"))
    peer = _Oct2pyPeer(oc)
    peer.tick(_dummy_in())
    return peer


def _session():
    global _SESSION, _LAST_IPC
    if _SESSION is not None:
        return _SESSION
    root = resolve_octave_planning()
    if root is None:
        raise FileNotFoundError(
            "octave_planning not found (need afc/m_lon_acc_aeb.m). "
            "Copy repo octave_planning next to carla_scenarios, or set GF_OCTAVE_PLANNING. "
            f"cwd={Path.cwd()} GF_OCTAVE_PLANNING={os.environ.get('GF_OCTAVE_PLANNING')!r}"
        )
    want = (os.environ.get("GF_OCTAVE_IPC") or "auto").strip().lower()
    print(f"[octave_bridge] Octave .m from {root}", flush=True)
    t0 = time.perf_counter()
    peer: Any = None
    err: Exception | None = None
    order = ipc_order(want, sys.platform)
    for kind in order:
        try:
            if kind == "pipe":
                peer = _start_pipe(root)
            elif kind == "stdio":
                peer = _start_stdio(root)
            elif kind == "tcp":
                peer = _start_tcp(root)
            elif kind == "file":
                peer = _start_file(root)
            else:
                peer = _start_oct2py(root)
            _LAST_IPC = peer.ipc
            dt = 1000.0 * (time.perf_counter() - t0)
            print(
                f"[octave_bridge] ipc={peer.ipc} warmed {dt:.0f}ms "
                f"(GF_OCTAVE_IPC={want})",
                flush=True,
            )
            _SESSION = peer
            return peer
        except Exception as exc:  # noqa: BLE001
            err = exc
            print(f"[octave_bridge] ipc={kind} failed: {exc}", flush=True)
            if peer is not None:
                try:
                    peer.close()
                except Exception:  # noqa: BLE001
                    pass
                peer = None
    raise RuntimeError(f"octave ipc failed ({order}): {err}")


def warm_octave() -> None:
    """Call from bridge main before listen so first perc is not a cold 2s+ tick."""
    _session()


def close_octave() -> None:
    global _SESSION, _D_SEE_PREV, _T_PLAN_PREV, _LAST_IPC
    oc = _SESSION
    _SESSION = None
    _D_SEE_PREV = 0.0
    _T_PLAN_PREV = 0.0
    _LAST_IPC = "none"
    if oc is not None:
        try:
            oc.close()
        except Exception:  # noqa: BLE001
            pass
    try:
        from _proc_util import kill_matching

        kill_matching("octave-cli")
        if sys.platform == "win32":
            kill_matching("octave.exe")
    except Exception:  # noqa: BLE001
        pass


def _lane_ok(perc: Any) -> bool:
    return (
        bool(perc.lane_valid)
        and abs(float(perc.e_y)) <= _LAT_EY_INVALID_M
        and abs(float(perc.c1)) <= _LAT_C1_INVALID
        and abs(float(perc.e_y)) <= _LAT_EY_SLOW_M
    )


# Same drop band as planning/driving ExtractPerc (kObjDMaxM).
_OBJ_D_MAX_M = 130.0


def _obj_row(o: Any) -> Optional[list[float]]:
    d = float(o.long_m)
    if int(getattr(o, "obj_id", 0) or 0) == 0 or d < 0.0 or d > _OBJ_D_MAX_M:
        return None
    cls = float(o.obj_class or 1)
    is_ped = 1.0 if (int(o.is_ped or 0) or int(cls) == 5) else 0.0
    return [
        d,
        float(o.rel_v_mps),
        float(o.lat_m),
        max(float(o.len_m or 4.5), 0.5),
        cls,
        float(o.heading_rad or 0.0),
        is_ped,
    ]


def _obj_already(rows: list[list[float]], d: float, lat: float) -> bool:
    for r in rows:
        if abs(r[0] - d) < 1.5 and abs(r[2] - lat) < 0.8:
            return True
    return False


def _pack_obj(perc: Any) -> list[list[float]]:
    """n×7: d, rel, lat, len, cls, heading, is_ped. Same order as ExtractPerc.

    Empty → [] (nobj=0). ``_dummy_in`` stays FFI warmup only, not a scene pack.
    CIPV first, then the rest. Lead-only (no dyn) matches FCM FillOutFromTruth.
    """
    n_max = _OBJ_N_MAX
    rows: list[list[float]] = []
    objs = list(perc.objects or [])
    cipv_id = int(getattr(perc, "cipv_id", 0) or 0)
    if cipv_id:
        for o in objs:
            if int(o.obj_id) == cipv_id:
                rec = _obj_row(o)
                if rec is not None:
                    rows.append(rec)
                break
    elif perc.lead_valid and not objs:
        d = float(perc.lead_distance_m)
        if 0.0 <= d <= _OBJ_D_MAX_M:
            rows.append(
                [
                    d,
                    float(perc.lead_rel_speed_mps),
                    float(perc.lead_lat_m),
                    4.5,
                    1.0,
                    float(getattr(perc, "lead_heading_rad", 0.0) or 0.0),
                    0.0,
                ]
            )
    for o in objs:
        rec = _obj_row(o)
        if rec is None or _obj_already(rows, rec[0], rec[2]):
            continue
        if len(rows) >= n_max:
            break
        rows.append(rec)
    return rows[:n_max]


def _pack_in(view: PlanningView) -> list[float]:
    perc = view.perc
    ego = view.ego
    rows = _pack_obj(perc)
    vec = [0.0] * _IN_N
    vec[0] = float(ego.speed_mps)
    vec[1] = float(ego.steer_angle_deg)
    vec[2] = _b01(perc.lane_valid)
    vec[3] = float(perc.e_y)
    vec[4] = float(perc.c0)
    vec[5] = float(perc.c1)
    vec[6] = float(perc.c2)
    vec[7] = float(perc.c3)
    vec[8] = float(perc.x_end)
    vec[9] = float(perc.lane_conf)
    # Same as HostLaneFromPerc: 1, or 2 if adj present. .m only tests >= 2.
    lane_n = 1.0
    if perc.lane_valid and perc.adj:
        lane_n = 2.0
    vec[10] = lane_n
    vec[11] = float(_D_SEE_PREV)
    vec[12] = float(_T_PLAN_PREV)
    n = min(_OBJ_N_MAX, len(rows))
    vec[13] = float(n)
    for i in range(n):
        rec = rows[i]
        b = _IN_HDR + i * _OBJ_W
        for j in range(min(_OBJ_W, len(rec))):
            vec[b + j] = float(rec[j])
    return vec


def unpack_plan_vec(raw: Any) -> dict[str, Any]:
    """Decode m_plan_tick_pack row. Used by plan_tick and unit tests."""
    vals = _as_vec(raw)
    if len(vals) < _OUT_HDR:
        raise ValueError(f"plan pack short: {len(vals)}")
    n_pts = int(round(vals[12]))
    n_pts = max(0, min(_TRAJ_N, n_pts))
    xs = vals[_OUT_HDR:_OUT_HDR + _TRAJ_N]
    ys = vals[_OUT_HDR + _TRAJ_N:_OUT_HDR + 2 * _TRAJ_N]
    vs = vals[_OUT_HDR + 2 * _TRAJ_N:_OUT_HDR + 3 * _TRAJ_N]
    if n_pts:
        xs, ys, vs = xs[:n_pts], ys[:n_pts], vs[:n_pts]
    mid = int(round(vals[10]))
    mode = CTRL_MODE_NAMES.get(mid, "cruise")
    return {
        "throttle": vals[0],
        "brake": vals[1],
        "steer": vals[2],
        "target_speed_mps": vals[3],
        "D_see": vals[4],
        "T_plan": vals[5],
        "D_occ": vals[6],
        "a_req": vals[7],
        "horizon_m": vals[8],
        "allow_lc": vals[9],
        "mode": mode,
        "t_m_s": vals[11],
        "x_m": xs,
        "y_m": ys,
        "v_mps": vs,
    }


def plan_tick(view: PlanningView, *, seq: int = 0) -> PlanningResult:
    global _LAST_PLAN_LOG, _D_SEE_PREV, _T_PLAN_PREV
    global _LAST_PLAN_WALL_S, _LAST_PLAN_M_S, _LAST_PLAN_FFI_S
    peer = _session()
    perc = view.perc
    ego = view.ego
    t0 = time.perf_counter()
    raw: Any = None
    last_exc: Exception | None = None
    for _try in range(4):
        try:
            raw = peer.tick(_pack_in(view))
            break
        except OSError as exc:
            last_exc = exc
            time.sleep(0.004 * (_try + 1))
    if raw is None:
        raise last_exc if last_exc else RuntimeError("plan ipc failed")
    wall_s = time.perf_counter() - t0
    unpacked = unpack_plan_vec(raw)
    m_s = float(unpacked["t_m_s"])
    if m_s < 0.0 or m_s > wall_s + 0.05:
        m_s = 0.0
    ffi_s = max(0.0, wall_s - m_s)
    _LAST_PLAN_WALL_S = wall_s
    _LAST_PLAN_M_S = m_s
    _LAST_PLAN_FFI_S = ffi_s
    mode = str(unpacked["mode"])
    thr = float(unpacked["throttle"])
    brk = float(unpacked["brake"])
    tgt = float(unpacked["target_speed_mps"])
    steer = float(unpacked["steer"])
    D_see = float(unpacked["D_see"])
    T_plan = float(unpacked["T_plan"])
    _D_SEE_PREV = D_see
    _T_PLAN_PREV = T_plan
    xs = list(unpacked["x_m"])
    ys = list(unpacked["y_m"])
    vs = list(unpacked["v_mps"])
    a_req = float(unpacked["a_req"])
    D_occ = float(unpacked["D_occ"])
    allow_lc = int(unpacked["allow_lc"])
    horizon_m = float(unpacked["horizon_m"])

    now = time.monotonic()
    if plan_log_enabled() and (now - _LAST_PLAN_LOG) >= 0.5:
        _LAST_PLAN_LOG = now
        print(
            f"[octave_bridge] .m {mode} thr={thr:.2f} brk={brk:.2f} "
            f"v_plan={tgt:.1f} a_req={a_req:.2f} "
            f"Dsee={D_see:.0f} T={T_plan:.1f} Docc={D_occ:.0f} "
            f"lc={allow_lc} steer={steer:.2f} "
            f"v={ego.speed_mps:.1f} ey={perc.e_y:.2f} "
            f"lane={int(perc.lane_valid)} use={int(_lane_ok(perc))} "
            f"nobj={len(perc.objects)} lead={int(perc.lead_valid)} "
            f"d={perc.lead_distance_m:.1f} lat={perc.lead_lat_m:.1f}",
            flush=True,
        )

    return PlanningResult(
        stamp_ns=view.stamp_ns,
        seq=seq,
        throttle=thr,
        brake=brk,
        steer=steer,
        target_speed_mps=tgt,
        ctrl_mode=mode,
        points_x_m=xs,
        points_y_m=ys,
        points_v_mps=vs,
        horizon_m=horizon_m,
        D_see_m=D_see,
        T_plan_s=T_plan,
        allow_lc=allow_lc,
        lane_code=lane_code_from_path(ys),
    )
