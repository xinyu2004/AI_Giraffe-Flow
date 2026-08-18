# gf_channel (image plane shm)

Large image-plane shared-memory channel (Create/Open + multi-buffer YUV/RGB).
Formerly called `tip_channel` / TipChannel — not an industry acronym.

Compat: `gf_tip_*` macros and `gf_tip::channel` CMake alias still work for one transition.
Default slot name: `gf.channel.front` (legacy `gf.tip.front` still openable if created with that name).
