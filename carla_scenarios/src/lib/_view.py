"""Pygame scenario window: toggle chase modes.

Lab HMI only. Product camera stays on carla_bridge — view mode never moves camera.

ChaseCam (carla.env) ↔ config/spectator/*.mount.json:
  1 = windshield
  2 = bev_afc   (lab chase; attach-relative — previously tuned)
  3 = bev_adc   (lab chase; attach-relative)
  4 = overhead

Pygame RGB is attach_to ego (relative xyz/pitch/fov from spectator JSON).
UE spectator follows ChaseCam. Modes 2/3 place ego on screen
(2 a bit below center, 3 near center). Mode 3 is pulled in along the mount.
Mode 4 copies the overhead mount (near vertical). Not Foxglove paint canvas.

GF_CHASE_GHOST_OCCLUDERS: Cam 2/3/4 hide Bridge/Roads blocking ego (pose fixed).
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable, Optional

from _instrument import ClusterState, draw_cluster
from _camera_mount import (
    CameraMount,
    SPECTATOR_BY_ENV,
    load_camera_mount,
    load_spectator_mount,
    spectator_pose,
)
from _chase_ghost import ChaseGhostOccluders
from _chase_ground import profile_for_mode, solve_spectator_along_mount
from _perf import PerfAgg

MODE_WINDSHIELD = "1"
MODE_BEV_AFC = "2"
MODE_BEV_ADC = "3"
MODE_OVERHEAD = "4"

# Backward aliases used by older call sites
MODE_SCENE = MODE_BEV_AFC

_CYCLE = (MODE_WINDSHIELD, MODE_BEV_AFC, MODE_BEV_ADC, MODE_OVERHEAD)


def scenario_view_wanted(snap: Any = None) -> bool:
    """Prefer Snapshot.view; fallback for CLI tools that have not loaded snap."""
    if snap is not None:
        return bool(snap.view)
    v = (os.environ.get("GF_SCENARIO_VIEW") or "1").strip().lower()
    return v not in ("0", "off", "false", "no")


def resolve_chase_cam_mode(raw: Optional[str] = None) -> str:
    """ChaseCam: 1=windshield, 2=bev_afc, 3=bev_adc, 4=overhead."""
    if raw is None:
        raw = os.environ.get("ChaseCam") or "3"
    v = str(raw).strip().lower()
    if v in ("1", "mobileye_windshield", "windshield", MODE_WINDSHIELD):
        return MODE_WINDSHIELD
    if v in ("2", "scene", "chase", "bev_afc", "afc", MODE_BEV_AFC):
        return MODE_BEV_AFC
    if v in ("3", "bev_adc", "adc", MODE_BEV_ADC):
        return MODE_BEV_ADC
    if v in ("4", "overhead", "parking", "bev", MODE_OVERHEAD):
        # bare "bev" kept as overhead alias for old scripts; prefer bev_afc/bev_adc
        return MODE_OVERHEAD
    return MODE_WINDSHIELD


def _empty_surfaces() -> dict[str, Any]:
    return {m: None for m in _CYCLE}


class ScenarioView:
    """One RGB sensor → pygame (second cam spawned on V toggle)."""

    def __init__(
        self,
        world: Any,
        vehicle: Any,
        *,
        width: int = 960,
        height: int = 540,
        title: str = "AFC scenario",
        follow_spectator: bool = True,
        camera_mount: Optional[CameraMount] = None,
        initial_mode: Optional[str] = None,
        chase_cam: Optional[str] = None,
    ) -> None:
        import carla  # type: ignore
        import pygame

        self._carla = carla
        self._pygame = pygame
        self._world = world
        self._vehicle = vehicle
        self._follow_spectator = follow_spectator
        self._mount = camera_mount or load_camera_mount()
        mode_src = initial_mode if initial_mode is not None else chase_cam
        mode = resolve_chase_cam_mode(mode_src)
        self._mode = mode
        self._surfaces: dict[str, Any] = _empty_surfaces()
        self._hud_lines: list[str] = []
        self._cluster: Optional[ClusterState] = None
        self._cameras: dict[str, Any] = {}

        pygame.init()
        pygame.font.init()
        w = int(width)
        h = int(height)
        self.width = w
        self.height = h
        self._display = pygame.display.set_mode((w, h), pygame.DOUBLEBUF)
        pygame.display.set_caption(str(title))
        font_name = pygame.font.get_default_font()
        self._font = pygame.font.Font(font_name, 18)
        self._font_sm = pygame.font.Font(font_name, 16)
        self._fonts = {
            "sm": pygame.font.Font(font_name, 15),
            "md": pygame.font.Font(font_name, 18),
            "lg": pygame.font.Font(font_name, 28),
            "xl": pygame.font.Font(font_name, 64),
        }
        self._clock = pygame.time.Clock()
        self._perf = PerfAgg("pygame")
        self._ghost = ChaseGhostOccluders(world, carla)

        self._ensure_cam(self._mode)
        self._sync_spectator()
        m = self._mount_for(self._mode)
        print(
            f"[view] pygame ChaseCam mode={self._mode} "
            f"({SPECTATOR_BY_ENV.get(self._mode, '?')}; V cycles 1/2/3/4) "
            f"attach fov={m.fov:.0f} size={w}x{h} "
            f"(perception camera still owned by bridge)",
            flush=True,
        )

    def _mount_for(self, mode: str) -> CameraMount:
        if mode == MODE_WINDSHIELD:
            return self._mount
        name = SPECTATOR_BY_ENV.get(mode, "bev_adc")
        return load_spectator_mount(name)

    def _ensure_cam(self, mode: str) -> None:
        if self._cameras.get(mode) is not None:
            return
        carla = self._carla
        name = SPECTATOR_BY_ENV.get(mode)
        if name and mode != MODE_WINDSHIELD:
            cx, cz, cpitch, cyaw, cfov = spectator_pose(name)
            self._cameras[mode] = self._spawn_cam(
                fov=cfov,
                transform=carla.Transform(
                    carla.Location(x=cx, z=cz),
                    carla.Rotation(pitch=cpitch, yaw=cyaw),
                ),
                mode=mode,
            )
            return
        # Mode 1: product front contract; spectator/windshield as fallback.
        try:
            m = self._mount
            self._cameras[mode] = self._spawn_cam(
                fov=m.fov,
                transform=m.as_carla_transform(carla),
                mode=mode,
            )
        except Exception:  # noqa: BLE001
            wm = load_spectator_mount("windshield")
            self._cameras[mode] = self._spawn_cam(
                fov=wm.fov,
                transform=wm.as_carla_transform(carla),
                mode=mode,
            )

    def _spawn_cam(self, *, fov: float, transform: Any, mode: str) -> Any:
        bp = self._world.get_blueprint_library().find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(self.width))
        bp.set_attribute("image_size_y", str(self.height))
        bp.set_attribute("fov", str(float(fov)))
        cam = self._world.spawn_actor(bp, transform, attach_to=self._vehicle)

        def _on_image(image: Any, m: str = mode) -> None:
            # CARLA gives BGRA; pygame 2 can ingest it without a Python pixel loop.
            raw = bytes(image.raw_data)
            w, h = int(image.width), int(image.height)
            try:
                surf = self._pygame.image.frombuffer(raw, (w, h), "BGRA")
                self._surfaces[m] = surf.convert()
            except Exception:  # noqa: BLE001
                rgb = bytearray(w * h * 3)
                for i in range(w * h):
                    rgb[i * 3 + 0] = raw[i * 4 + 2]
                    rgb[i * 3 + 1] = raw[i * 4 + 1]
                    rgb[i * 3 + 2] = raw[i * 4 + 0]
                self._surfaces[m] = self._pygame.image.frombuffer(
                    bytes(rgb), (w, h), "RGB"
                )

        cam.listen(_on_image)
        return cam

    def reset_perf(self) -> None:
        """Call at case READY so [perf][pygame] does not fold in inter-case gaps."""
        self._perf.reset()

    def retarget_vehicle(self, vehicle: Any) -> None:
        """Move chase cams onto a new hero without closing the pygame window."""
        if vehicle is None:
            return
        try:
            if int(getattr(self._vehicle, "id", -1)) == int(getattr(vehicle, "id", -2)):
                return
        except Exception:  # noqa: BLE001
            pass
        for cam in list(self._cameras.values()):
            try:
                cam.stop()
            except Exception:  # noqa: BLE001
                pass
            try:
                cam.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._cameras.clear()
        self._surfaces = _empty_surfaces()
        self._vehicle = vehicle
        # Ghost catalog is process-once; do not restore_all on case retarget
        # (T_clear fades old ids — avoids flash + catalog rebuild stutter).
        self._ensure_cam(self._mode)
        self._sync_spectator()
        print(
            f"[view] retarget chase cam → ego id={getattr(vehicle, 'id', '?')} "
            f"mode={self._mode} (pygame window kept)",
            flush=True,
        )

    def mode(self) -> str:
        return self._mode

    def camera_mount(self) -> CameraMount:
        return self._mount

    def toggle_mode(self) -> str:
        try:
            i = _CYCLE.index(self._mode)
        except ValueError:
            i = 0
        nxt = _CYCLE[(i + 1) % len(_CYCLE)]
        self._ensure_cam(nxt)
        self._mode = nxt
        if self._mode == MODE_WINDSHIELD:
            self._ghost.restore_all()
        self._sync_spectator()
        name = SPECTATOR_BY_ENV.get(self._mode, "?")
        print(
            f"[view] display={self._mode}/{name} (perception camera unchanged)",
            flush=True,
        )
        return self._mode

    def _sync_spectator(self) -> None:
        """UE spectator follows ChaseCam.

        Elevated 2/3: pitch places ego (2 below center, 3 near center).
        Mode 3 is scaled in along the mount so it is not a tiny overview.
        Mode 1 and 4 copy the mount (4 stays near-nadir).
        """
        if not self._follow_spectator:
            return
        try:
            m = self._mount_for(self._mode)
            sx, sy, sz = float(m.x), float(m.y), float(m.z)
            pitch = float(m.pitch)
            if self._mode not in (MODE_WINDSHIELD, MODE_OVERHEAD):
                try:
                    ue_fov = float((os.environ.get("GF_SPECTATOR_FOV") or "100").strip())
                except ValueError:
                    ue_fov = 100.0
                ue_fov = max(60.0, min(120.0, ue_fov))
                aspect = float(self.width) / max(1.0, float(self.height))
                sx, sz, pitch, _ef, _er = solve_spectator_along_mount(
                    float(m.x),
                    float(m.z),
                    float(m.pitch),
                    float(m.fov),
                    aspect,
                    ue_fov,
                    profile=profile_for_mode(self._mode),
                )
            tf = self._vehicle.get_transform()
            fwd = tf.get_forward_vector()
            right = tf.get_right_vector()
            up = tf.get_up_vector()
            loc = tf.location
            cam_loc = self._carla.Location(
                x=loc.x + fwd.x * sx + right.x * sy + up.x * sz,
                y=loc.y + fwd.y * sx + right.y * sy + up.y * sz,
                z=loc.z + fwd.z * sx + right.z * sy + up.z * sz,
            )
            rot = self._carla.Rotation(
                pitch=tf.rotation.pitch + pitch,
                yaw=tf.rotation.yaw + m.yaw,
                roll=0.0,
            )
            self._world.get_spectator().set_transform(
                self._carla.Transform(cam_loc, rot)
            )
        except Exception:  # noqa: BLE001
            pass

    def set_hud(self, lines: list[str]) -> None:
        """Legacy text lines (used only when no cluster is set)."""
        self._hud_lines = list(lines)

    def set_cluster(self, state: ClusterState) -> None:
        """Instrument layer (preferred). Same frame size as the camera blit."""
        self._cluster = state

    def pump(self) -> bool:
        """Draw one frame. Returns False if user closed the window."""
        pygame = self._pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                # Silent toggle (no on-screen View/V chrome).
                if event.key == pygame.K_v:
                    self.toggle_mode()

        self._sync_spectator()
        self._ghost.pump(
            mode=self._mode,
            camera=self._cameras.get(self._mode),
            vehicle=self._vehicle,
        )
        self._display.fill((0, 0, 0))
        surface = self._surfaces.get(self._mode)
        if surface is not None:
            self._display.blit(surface, (0, 0))
        if self._cluster is not None:
            import time as _time

            self._cluster.now_s = _time.time()
            self._cluster.cam_mode = str(self._mode)
            draw_cluster(pygame, self._display, self._fonts, self._cluster)
        else:
            y = 8
            for line in self._hud_lines:
                surf = self._font.render(line, True, (240, 240, 240))
                self._display.blit(surf, (10, y))
                y += 22
        pygame.display.flip()
        self._clock.tick(30)
        fps = float(self._clock.get_fps())
        self._perf.tick(
            extra={
                "pygame_fps": f"{fps:.1f}",
                "size": f"{self.width}x{self.height}",
                "cams": f"{len(self._cameras)}",
                "clock": "V",
            }
        )
        return True

    def destroy(self) -> None:
        try:
            self._ghost.destroy()
        except Exception:  # noqa: BLE001
            pass
        for cam in self._cameras.values():
            try:
                cam.stop()
                cam.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._cameras.clear()
        try:
            self._pygame.quit()
        except Exception:  # noqa: BLE001
            pass


# Backward-compatible name (AEB etc.).
ChaseCam = ScenarioView


def gap_speed(ego: Any, lead: Any) -> tuple[float, float, float, float]:
    """Return (gap_m, ego_mps, lead_mps, rel_mps)."""
    a = ego.get_location()
    b = lead.get_location()
    gap = math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
    ev = ego.get_velocity()
    lv = lead.get_velocity()
    es = math.sqrt(ev.x**2 + ev.y**2 + ev.z**2)
    ls = math.sqrt(lv.x**2 + lv.y**2 + lv.z**2)
    return gap, es, ls, ls - es


def run_loop(
    *,
    stop_flag: Callable[[], bool],
    tick: Callable[[], None],
    view: ScenarioView,
    period_s: float,
) -> None:
    import time

    while not stop_flag():
        tick()
        if not view.pump():
            break
        time.sleep(max(0.0, period_s - 0.001))
