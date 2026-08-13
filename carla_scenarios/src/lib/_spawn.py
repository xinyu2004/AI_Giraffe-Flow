"""Compatibility re-export only — implementation lives in ``src/spawn/``.

Do not add business logic here. Layouts should prefer ``from spawn.X import …``.
"""

from __future__ import annotations

# Ensure src/ is on path when cases only insert src/lib.
from _afc_path import ensure_afc_path

ensure_afc_path()

from spawn.boundary import handoff_keep_ego, sanitize_keep_ego  # noqa: E402
from spawn.ic import (  # noqa: E402
    closing_along_heading,
    closing_along_pose,
    closing_toward_lead,
    enable_constant_forward,
    release_only,
    reset_vehicle_motion,
    seed_speed,
    set_forward_speed,
)
from spawn.pick import (  # noqa: E402
    offset_transform,
    pick_curve_transform,
    pick_cut_in_transforms,
    pick_follow_transforms,
)
from spawn.place import (  # noqa: E402
    spawn_ego_lead,
    spawn_ego_only,
    spawn_named,
    spawn_walker_at,
)
from spawn.roles import (  # noqa: E402
    ROLE_EGO,
    ROLE_LEAD,
    clear_near,
    destroy_role,
    find_by_role,
    set_role as _set_role,
    tick_world as _tick_world,
)

# Legacy private name used by older call sites / mental model.
_reset_vehicle_motion = reset_vehicle_motion

__all__ = [
    "ROLE_EGO",
    "ROLE_LEAD",
    "_reset_vehicle_motion",
    "_set_role",
    "_tick_world",
    "clear_near",
    "closing_along_heading",
    "closing_along_pose",
    "closing_toward_lead",
    "destroy_role",
    "enable_constant_forward",
    "find_by_role",
    "handoff_keep_ego",
    "offset_transform",
    "pick_curve_transform",
    "pick_cut_in_transforms",
    "pick_follow_transforms",
    "release_only",
    "reset_vehicle_motion",
    "sanitize_keep_ego",
    "seed_speed",
    "set_forward_speed",
    "spawn_ego_lead",
    "spawn_ego_only",
    "spawn_named",
    "spawn_walker_at",
]
