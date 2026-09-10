"""ProjectSession lives in ``gf_config.core``; this module documents layers.

Layers (do not reverse):
  names              — pure service/channel naming
  validate           — pure in-memory gates (no I/O, no mutation)
  core               — ProjectSession: sole YAML + dirty_* writer
  gui/pipeline       — flush → validate → save/compose façade
  gui/wiring_rebuild — paint-only graph rebuild
  gui/ara_constants / ara_widgets / ara_pages / ara_tables /
    ara_load / ara_commit — platform tab split-outs
  gui/editor_history — shared DocHistory hooks mixin
  gui/*              — widgets call session APIs only
"""

from gf_config.core import ProjectSession

__all__ = ["ProjectSession"]
