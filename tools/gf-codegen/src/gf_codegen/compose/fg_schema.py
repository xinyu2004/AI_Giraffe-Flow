"""Normalize / validate AUTOSAR-like Function Group authoring (exec.yaml)."""

from __future__ import annotations

from typing import Any

_MACHINE_STATES = frozenset({"Off", "Running", "Updating"})
_KIND_MACHINE = "machine"
_KIND_MODE = "mode"


def normalize_fg_kind(raw: Any, *, initial: str = "", states: list[str] | None = None) -> str:
    """Infer kind when omitted: classic Machine initials → machine; else mode."""
    k = str(raw or "").strip().lower()
    if k in (_KIND_MACHINE, "classic", "machine_fg"):
        return _KIND_MACHINE
    if k in (_KIND_MODE, "named", "mode_declaration", "modedeclaration"):
        return _KIND_MODE
    if states:
        return _KIND_MODE
    if initial in _MACHINE_STATES or initial == "":
        return _KIND_MACHINE
    return _KIND_MODE


def normalize_function_groups(fgs: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(fgs, list):
        return [{"id": "MachineFG", "kind": _KIND_MACHINE, "initial": "Running", "states": []}]
    for fg in fgs:
        if not isinstance(fg, dict):
            continue
        fid = str(fg.get("id") or "").strip()
        if not fid:
            continue
        initial = str(fg.get("initial") or "").strip()
        states_raw = fg.get("states")
        states: list[str] = []
        if isinstance(states_raw, list):
            states = [str(s).strip() for s in states_raw if str(s).strip()]
        kind = normalize_fg_kind(fg.get("kind"), initial=initial, states=states)
        if kind == _KIND_MACHINE:
            if initial not in _MACHINE_STATES:
                initial = "Running"
            states = []
        else:
            if not states and initial:
                states = [initial]
            if not initial and states:
                initial = states[0]
            if initial and initial not in states:
                states = [initial] + states
        out.append({"id": fid, "kind": kind, "initial": initial, "states": states})
    if not out:
        out.append({"id": "MachineFG", "kind": _KIND_MACHINE, "initial": "Running", "states": []})
    return out


def normalize_active_in(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def normalize_exec_process(proc: dict[str, Any]) -> dict[str, Any]:
    """Drop legacy drive_park_state; map to active_in when present."""
    entry = dict(proc)
    legacy = entry.pop("drive_park_state", None)
    active = normalize_active_in(entry.get("active_in"))
    if not active and legacy is not None:
        active = normalize_active_in(legacy)
    if active:
        entry["active_in"] = active
    else:
        entry.pop("active_in", None)
    if not str(entry.get("function_group") or "").strip():
        entry["function_group"] = "MachineFG"
    return entry


def validate_exec_function_groups(
    exec_data: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for FG kind / active_in consistency."""
    errors: list[str] = []
    warnings: list[str] = []
    fgs = normalize_function_groups(exec_data.get("function_groups"))
    by_id = {fg["id"]: fg for fg in fgs}
    for fg in fgs:
        if fg["kind"] == _KIND_MACHINE and fg.get("states"):
            warnings.append(
                f"function_group {fg['id']}: kind=machine ignores states {fg['states']}"
            )
        if fg["kind"] == _KIND_MODE and not fg.get("states"):
            errors.append(f"function_group {fg['id']}: kind=mode requires states[]")
        if fg["kind"] == _KIND_MODE and fg.get("initial") and fg["initial"] not in fg["states"]:
            errors.append(
                f"function_group {fg['id']}: initial {fg['initial']!r} not in states"
            )
    for i, proc in enumerate(exec_data.get("processes") or []):
        if not isinstance(proc, dict):
            continue
        name = str(proc.get("name") or "").strip() or f"processes[{i}]"
        fg_id = str(proc.get("function_group") or "MachineFG").strip()
        if fg_id not in by_id:
            errors.append(f"exec process {name}: unknown function_group {fg_id}")
            continue
        fg = by_id[fg_id]
        # legacy field should not remain after normalize; still reject if author left it
        if "drive_park_state" in proc and proc.get("drive_park_state") is not None:
            warnings.append(
                f"exec process {name}: drive_park_state is removed; use active_in"
            )
        active = normalize_active_in(proc.get("active_in"))
        if not active and proc.get("drive_park_state") is not None:
            active = normalize_active_in(proc.get("drive_park_state"))
        if fg["kind"] == _KIND_MACHINE and active:
            errors.append(
                f"exec process {name}: active_in not allowed on machine FG {fg_id}"
            )
        if fg["kind"] == _KIND_MODE:
            if not active:
                errors.append(
                    f"exec process {name}: mode FG {fg_id} requires active_in[]"
                )
            else:
                for st in active:
                    if st not in fg["states"]:
                        errors.append(
                            f"exec process {name}: active_in state {st!r} "
                            f"not in {fg_id}.states"
                        )
    return errors, warnings
