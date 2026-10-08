"""Authored values vs widget display defaults.

Three session bags (req / wiring / ara_cfg) share one rule:

- Missing keys stay missing (canvas ``set_node_ui`` already).
- Extra keys the form does not edit stay on disk.
- Hex / int ids that mean the same number are not a change (YAML ``0xF100``).

Display defaults (empty EM args shown as ``0``, log ``file_max_bytes`` spin)
must not be written by harvest; this module only folds form output onto disk.
"""

from __future__ import annotations

from typing import Any


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text, 0)
        except ValueError:
            return None
    return None


def values_equiv(left: Any, right: Any) -> bool:
    """Structural equality with hex/int id coercion."""
    if left is right or left == right:
        return True
    li, ri = _as_int(left), _as_int(right)
    if li is not None and ri is not None and li == ri:
        return True
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(values_equiv(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(values_equiv(a, b) for a, b in zip(left, right))
    return False


def _record_ident(row: dict[str, Any]) -> tuple[str, Any] | None:
    for key in ("id", "name"):
        val = row.get(key)
        if val is not None and val != "":
            return key, val
    return None


def _records(rows: list[Any]) -> bool:
    return all(isinstance(x, dict) for x in rows)


def _match_record(
    old: list[Any], new_row: dict[str, Any], used: list[bool]
) -> int | None:
    ident = _record_ident(new_row)
    if ident is None:
        return None
    kind, val = ident
    for i, prev in enumerate(old):
        if used[i] or not isinstance(prev, dict):
            continue
        if kind not in prev:
            continue
        if values_equiv(prev.get(kind), val):
            return i
    return None


def _merge_record_list(old: list[Any], new: list[Any]) -> tuple[list[Any], bool]:
    used = [False] * len(old)
    out: list[Any] = []
    for row in new:
        if not isinstance(row, dict):
            out.append(row)
            continue
        idx = _match_record(old, row, used)
        if idx is None:
            out.append(row)
            continue
        used[idx] = True
        merged, _ = merge_authored(old[idx], row)
        out.append(merged)
    dropped = any(not u for u in used)
    changed = dropped or len(out) != len(old)
    if not changed:
        changed = any(not values_equiv(a, b) for a, b in zip(old, out))
    return out, changed


def merge_authored(old: Any, new: Any) -> tuple[Any, bool]:
    """Fold form ``new`` onto disk ``old``. Keep extra keys and original id form.

    Returns ``(value_to_store, changed)``.
    """
    if values_equiv(old, new):
        return old, False
    if isinstance(old, dict) and isinstance(new, dict):
        out = dict(old)
        changed = False
        for key, nv in new.items():
            if key not in out:
                out[key] = nv
                changed = True
                continue
            merged, ch = merge_authored(out[key], nv)
            if ch:
                out[key] = merged
                changed = True
        return out, changed
    if isinstance(old, list) and isinstance(new, list) and _records(old) and _records(new):
        return _merge_record_list(old, new)
    return new, True
