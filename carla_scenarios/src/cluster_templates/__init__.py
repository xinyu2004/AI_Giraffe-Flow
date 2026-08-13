"""Per-feature instrument templates (add a module for a new feature)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import acc as acc_mod
from . import aeb as aeb_mod
from . import common as common_mod
from . import hlb as hlb_mod
from . import lateral as lateral_mod
from . import tsr as tsr_mod

DrawFn = Callable[..., None]

_REGISTRY: dict[str, DrawFn] = {
    "common": common_mod.draw_feature,
    "acc": acc_mod.draw_feature,
    "follow": acc_mod.draw_feature,
    "aeb": aeb_mod.draw_feature,
    "fcw": aeb_mod.draw_feature,
    "lateral": lateral_mod.draw_feature,
    "lka": lateral_mod.draw_feature,
    "ldw": lateral_mod.draw_feature,
    "elk": lateral_mod.draw_feature,
    "lcc": lateral_mod.draw_feature,
    "hlb": hlb_mod.draw_feature,
    "tsr": tsr_mod.draw_feature,
    "isa": tsr_mod.draw_feature,
}


def resolve_template(name: Optional[str]) -> DrawFn:
    key = (name or "common").strip().lower()
    return _REGISTRY.get(key) or _REGISTRY["common"]
