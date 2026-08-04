"""Minimal ISO 13400-2 DoIP TCP client for GMT OTA sheet (SIL)."""

from __future__ import annotations

import socket
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Optional

DOIP_ROUTING_REQ = 0x0005
DOIP_ROUTING_RESP = 0x0006
DOIP_DIAG = 0x8001
DOIP_DIAG_ACK = 0x8002

ROUTING_OK = 0x10

# SIL stub key for 0x27 level 1 (see middleware/diag UdsDispatcher SilVerifyKey)
_SIL_KEY = bytes([0x55, 0xAA])

_SID_NAME = {
    0x10: "DiagnosticSessionControl",
    0x11: "ECUReset",
    0x14: "ClearDiagnosticInformation",
    0x19: "ReadDTCInformation",
    0x22: "ReadDataByIdentifier",
    0x27: "SecurityAccess",
    0x29: "Authentication",
    0x31: "RoutineControl",
    0x34: "RequestDownload",
    0x36: "TransferData",
    0x37: "RequestTransferExit",
    0x38: "RequestFileTransfer",
    0x3E: "TesterPresent",
    0x85: "ControlDTCSetting",
}

OTA_MODE_FILE = "request_file_transfer"
OTA_MODE_DOWNLOAD = "request_download"
OTA_MODE_ROUTINE = "routine_sil"


def uds_sid_name(sid: int) -> str:
    return _SID_NAME.get(sid & 0xFF, f"SID_0x{sid & 0xFF:02X}")


def format_uds_step(req: bytes, resp: bytes) -> str:
    """One-line GMT/SIL-style UDS step for the log pane."""
    name = uds_sid_name(req[0]) if req else "?"
    if not resp:
        return f"UDS 0x{req[0]:02X} {name}  req={req.hex()}  resp=(suppress)  [OK]"
    ok = resp[0] != 0x7F
    tag = "OK" if ok else "NRC"
    return f"UDS 0x{req[0]:02X} {name}  req={req.hex()}  resp={resp.hex()}  [{tag}]"


def _encode(payload_type: int, payload: bytes, version: int = 0x02) -> bytes:
    return struct.pack("!BBHI", version, (~version) & 0xFF, payload_type, len(payload)) + payload


def _try_decode(buf: bytes) -> tuple[Optional[tuple[int, bytes]], int]:
    """Returns ((ptype, payload), consumed) or (None, 0) if need more; (None, n) to drop n."""
    if len(buf) < 8:
        return None, 0
    ver, inv, ptype, plen = struct.unpack("!BBHI", buf[:8])
    if ((~ver) & 0xFF) != inv:
        return None, 1
    if plen > 65536:
        return None, 1
    if len(buf) < 8 + plen:
        return None, 0
    return (ptype, buf[8 : 8 + plen]), 8 + plen


class DoipClient:
    def __init__(self) -> None:
        self._sock: Optional[socket.socket] = None
        self._buf = bytearray()
        self._default_timeout = 5.0
        self.tester = 0x0E80
        self.entity = 0x0E00

    def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.close()
        self._default_timeout = float(timeout)
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)
        self._sock = s
        self._buf.clear()

    def set_response_timeout(self, timeout: float) -> None:
        """Align with diag.yaml p2_star_server_ms (seconds)."""
        self._default_timeout = max(0.2, float(timeout))
        if self._sock is not None:
            self._sock.settimeout(self._default_timeout)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._buf.clear()

    def _send(self, data: bytes) -> None:
        assert self._sock is not None
        self._sock.sendall(data)

    def _recv_payload(self, expect_type: int) -> bytes:
        assert self._sock is not None
        while True:
            decoded, consumed = _try_decode(bytes(self._buf))
            if decoded is not None:
                del self._buf[:consumed]
                ptype, payload = decoded
                if ptype == expect_type:
                    return payload
                continue
            if consumed > 0:
                del self._buf[:consumed]
                continue
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("DoIP connection closed")
            self._buf.extend(chunk)

    def routing_activation(self) -> None:
        payload = struct.pack("!HB", self.tester, 0x00) + b"\x00\x00\x00\x00"
        self._send(_encode(DOIP_ROUTING_REQ, payload))
        resp = self._recv_payload(DOIP_ROUTING_RESP)
        if len(resp) < 5 or resp[4] != ROUTING_OK:
            raise RuntimeError(f"RoutingActivation denied: {resp.hex()}")

    def transceive(self, uds: bytes, *, allow_empty: bool = False) -> bytes:
        payload = struct.pack("!HH", self.tester, self.entity) + uds
        self._send(_encode(DOIP_DIAG, payload))
        self._recv_payload(DOIP_DIAG_ACK)
        if allow_empty and (uds[0] == 0x3E and (uds[1] & 0x80)):
            # suppressPosRsp: board may send only ACK
            self._sock.settimeout(0.05)  # type: ignore[union-attr]
            try:
                resp = self._recv_payload(DOIP_DIAG)
            except (TimeoutError, socket.timeout, OSError):
                return b""
            finally:
                self._sock.settimeout(getattr(self, "_default_timeout", 5.0))  # type: ignore[union-attr]
            if len(resp) < 4:
                return b""
            return resp[4:]
        resp = self._recv_payload(DOIP_DIAG)
        if len(resp) < 4:
            raise RuntimeError("short diagnostic response")
        return resp[4:]

    def tester_present(self, *, suppress: bool = False) -> bytes:
        sub = 0x80 if suppress else 0x00
        return self.transceive(bytes([0x3E, sub]), allow_empty=suppress)

    def start_ota(self, package_id: str, artifact_path: str) -> bytes:
        spec = f"{package_id}|{artifact_path}".encode("utf-8")
        return self.transceive(bytes([0x31, 0x01, 0xF1, 0x00]) + spec)

    def ota_progress(self) -> int:
        r = self.transceive(bytes([0x31, 0x03, 0xF1, 0x01]))
        if len(r) >= 5 and r[0] == 0x71:
            return int(r[4])
        return -1

    def run_ota_sequence(
        self,
        package_id: str,
        artifact_path: str,
        *,
        mode: str = OTA_MODE_FILE,
        max_block: int = 1024,
        require_programming: bool = True,
        require_security: bool = True,
        on_step: Callable[[str], None] | None = None,
    ) -> bytes:
        """Product OTA: session/security then 0x38|0x34 pipe (or routine_sil)."""

        def _step(req: bytes, *, allow_empty: bool = False) -> bytes:
            resp = self.transceive(req, allow_empty=allow_empty)
            line = format_uds_step(req, resp)
            if on_step is not None:
                on_step(line)
            if resp and resp[0] == 0x7F:
                nrc = resp[2] if len(resp) >= 3 else -1
                raise RuntimeError(f"{line} (NRC=0x{nrc:02X})")
            return resp

        # Programming session for flash; extended kept for routine_sil flexibility
        session_sf = 0x02 if require_programming else 0x03
        _step(bytes([0x10, session_sf]))

        if require_security:
            seed_resp = _step(bytes([0x27, 0x01]))
            if len(seed_resp) < 4 or seed_resp[0] != 0x67:
                raise RuntimeError(f"SecurityAccess seed unexpected: {seed_resp.hex()}")
            _step(bytes([0x27, 0x02]) + _SIL_KEY)

        mode_n = (mode or OTA_MODE_FILE).strip().lower()
        if mode_n in (OTA_MODE_ROUTINE, "0x31", "31", "sil"):
            spec = f"{package_id}|{artifact_path}".encode("utf-8")
            return _step(bytes([0x31, 0x01, 0xF1, 0x00]) + spec)

        data = Path(artifact_path).read_bytes() if artifact_path else b""
        if not data:
            # Allow empty/missing for dry-run: create tiny placeholder
            data = f"SIL-EMPTY:{package_id}\n".encode("utf-8")

        if mode_n in (OTA_MODE_DOWNLOAD, "0x34", "34"):
            # dataFormatId=0x00, alfi=0x44 (4-byte addr + 4-byte size), addr=0, size=len
            req34 = bytes([0x34, 0x00, 0x44, 0, 0, 0, 0]) + struct.pack("!I", len(data))
            resp34 = _step(req34)
            block = max_block
            if len(resp34) >= 6 and resp34[0] == 0x74:
                lfi = resp34[1]
                n = (lfi >> 4) & 0x0F
                if n and len(resp34) >= 2 + n:
                    block = int.from_bytes(resp34[2 : 2 + n], "big") or block
        else:
            # 0x38 replaceFile
            name = Path(artifact_path).name.encode("utf-8") or b"pkg.bin"
            if len(name) > 255:
                name = name[:255]
            req38 = (
                bytes([0x38, 0x03, len(name)])
                + name
                + bytes([0x00, 0x04])  # dataFormatId, sizeLen=4
                + struct.pack("!I", len(data))
                + struct.pack("!I", len(data))
            )
            resp38 = _step(req38)
            block = max_block
            if len(resp38) >= 7 and resp38[0] == 0x78:
                lfi = resp38[2]
                n = (lfi >> 4) & 0x0F
                if n and len(resp38) >= 3 + n:
                    block = int.from_bytes(resp38[3 : 3 + n], "big") or block

        block = max(8, min(block, max_block, 4095))
        seq = 1
        off = 0
        while off < len(data):
            chunk = data[off : off + block]
            resp36 = _step(bytes([0x36, seq & 0xFF]) + chunk)
            if not resp36 or resp36[0] != 0x76:
                raise RuntimeError(f"TransferData failed at seq={seq}")
            off += len(chunk)
            seq = 0 if seq == 0xFF else seq + 1
            if on_step is not None and (off == len(data) or off // block % 8 == 0):
                on_step(f"… transfer {off}/{len(data)} bytes")

        return _step(bytes([0x37]))

    def read_dtc_list(
        self,
        *,
        status_mask: int = 0xFF,
        on_step: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """0x19 0x02 — report DTC by status mask. Returns {code, status}."""
        req = bytes([0x19, 0x02, status_mask & 0xFF])
        resp = self.transceive(req)
        line = format_uds_step(req, resp)
        if on_step is not None:
            on_step(line)
        if not resp or resp[0] == 0x7F:
            nrc = resp[2] if resp and len(resp) >= 3 else -1
            raise RuntimeError(f"0x19 failed NRC=0x{nrc:02X}: {line}")
        if len(resp) < 3 or resp[0] != 0x59:
            raise RuntimeError(f"0x19 unexpected: {resp.hex()}")
        out: list[dict] = []
        body = resp[3:]  # skip 59 02 mask
        for i in range(0, len(body) - 3, 4):
            code = (body[i] << 16) | (body[i + 1] << 8) | body[i + 2]
            status = body[i + 3]
            out.append({"code": code, "status": status})
        return out

    def clear_dtcs(
        self,
        *,
        group: int = 0xFFFFFF,
        on_step: Callable[[str], None] | None = None,
    ) -> None:
        """0x14 ClearDiagnosticInformation."""
        req = bytes(
            [
                0x14,
                (group >> 16) & 0xFF,
                (group >> 8) & 0xFF,
                group & 0xFF,
            ]
        )
        resp = self.transceive(req)
        line = format_uds_step(req, resp)
        if on_step is not None:
            on_step(line)
        if not resp or resp[0] == 0x7F:
            nrc = resp[2] if resp and len(resp) >= 3 else -1
            raise RuntimeError(f"0x14 failed NRC=0x{nrc:02X}: {line}")

    def read_collector_events(
        self,
        *,
        offset: int = 0,
        max_n: int = 200,
        on_step: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """RID F201: dump EventCollector ring (NDJSON body). Same shape as store file."""
        import json

        req = bytes([0x31, 0x01, 0xF2, 0x01]) + struct.pack(
            "!HH", max(0, int(offset)), max(1, min(int(max_n), 500))
        )
        resp = self.transceive(req)
        line = format_uds_step(req, resp)
        if on_step is not None:
            on_step(line)
        if not resp or resp[0] == 0x7F:
            nrc = resp[2] if resp and len(resp) >= 3 else -1
            raise RuntimeError(f"Collector dump failed NRC=0x{nrc:02X}: {line}")
        if len(resp) < 10 or resp[0] != 0x71:
            raise RuntimeError(f"Collector dump unexpected: {resp.hex()}")
        # 0x71 01 F2 01 | total | offset | count | ndjson…
        payload = resp[10:]
        rows: list[dict] = []
        for raw in payload.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                rows.append(rec)
        return rows
