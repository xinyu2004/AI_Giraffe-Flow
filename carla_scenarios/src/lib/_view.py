"""Pygame scenario window: toggle scene chase ↔ windshield.

Lab HMI only. Product camera stays on carla_bridge — view mode never moves camera.

ChaseCam (carla.env): 1=windshield (default), 2=scene.
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable, Optional

from _instrument import ClusterState, draw_cluster
from _camera_mount import CameraMount, load_camera_mount, scene_chase_pose
from _perf import PerfAgg

MODE_SCENE = "2"
MODE_WINDSHIELD = "1"


def scenario_view_wanted() -> bool:
    """GF_SCENARIO_VIEW=0 skips pygame (iGPU bench). Default on."""
    v = (os.environ.get("GF_SCENARIO_VIEW") or "1").strip().lower()
    return v not in ("0", "off", "false", "no")


def resolve_chase_cam_mode(raw: Optional[str] = None) -> str:
    """ChaseCam from carla.env: 1=windshield (default), 2=scene."""
    if raw is None:
        try:
            from _carla_env import load_local_env

            load_local_env()
        except Exception:  # noqa: BLE001
            pass
        raw = os.environ.get("ChaseCam") or "1"
    v = str(raw).strip().lower()
    if v in ("1", "mobileye_windshield", "windshield", MODE_WINDSHIELD):
        return MODE_WINDSHIELD
    if v in ("2", "scene", "chase", MODE_SCENE):
        return MODE_SCENE
    return MODE_WINDSHIELD


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
    ) -> None:
        import carla  # type: ignore
        import pygame

        self._carla = carla
        self._pygame = pygame
        self._world = world
        self._vehicle = vehicle
        self._follow_spectator = follow_spectator
        self._mount = camera_mount or load_camera_mount()
        mode = (
            resolve_chase_cam_mode(initial_mode)
            if initial_mode is not None
            else resolve_chase_cam_mode()
        )
        self._mode = mode
        self._surfaces: dict[str, Any] = {MODE_SCENE: None, MODE_WINDSHIELD: None}
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

        self._ensure_cam(self._mode)
        self._sync_spectator()
        print(
            f"[view] pygame ChaseCam mode={self._mode} (1 cam, V spawns the other) "
            f"mount_ref={self._mount.describe()} (camera owned by bridge)",
            flush=True,
        )

    def _ensure_cam(self, mode: str) -> None:
        if self._cameras.get(mode) is not None:
            return
        carla = self._carla
        if mode == MODE_SCENE:
            cx, cz, cpitch, cyaw, cfov = scene_chase_pose()
            self._cameras[mode] = self._spawn_cam(
                fov=cfov,
                transform=carla.Transform(
                    carla.Location(x=cx, z=cz),
                    carla.Rotation(pitch=cpitch, yaw=cyaw),
                ),
                mode=mode,
            )
            return
        self._cameras[mode] = self._spawn_cam(
            fov=self._mount.fov,
            transform=self._mount.as_carla_transform(carla),
            mode=mode,
        )

    def _spawn_cam(self, *, fov: float, transform: Any, mode: str) -> Any:
        bp = self._world.get_blueprint_library().find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(self.width))
        bp.set_attribute("image_size_y", str(self.height))
        bp.set_attribute("fov", str(float(fov)))
        cam = self._world.spawn_actor(bp, transform, attach_to=self._vehicle)

        def _on_image(image: Any, m: str = mode) -> None:
            raw = bytes(image.raw_data)
            w, h = image.width, image.height
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
        self._surfaces = {MODE_SCENE: None, MODE_WINDSHIELD: None}
        self._vehicle = vehicle
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
        nxt = MODE_WINDSHIELD if self._mode == MODE_SCENE else MODE_SCENE
        self._ensure_cam(nxt)
        self._mode = nxt
        self._sync_spectator()
        print(f"[view] display={self._mode} (perception camera unchanged)", flush=True)
        return self._mode

    def _sync_spectator(self) -> None:
        if not self._follow_spectator:
            return
        try:
            tf = self._vehicle.get_transform()
            fwd = tf.get_forward_vector()
            loc = tf.location
            if self._mode == MODE_WINDSHIELD:
                # Approx world pose of windshield camera_mount.
                m = self._mount
                right = tf.get_right_vector()
                up = tf.get_up_vector()
                cam_loc = self._carla.Location(
                    x=loc.x + fwd.x * m.x + right.x * m.y + up.x * m.z,
                    y=loc.y + fwd.y * m.x + right.y * m.y + up.y * m.z,
                    z=loc.z + fwd.z * m.x + right.z * m.y + up.z * m.z,
                )
                rot = self._carla.Rotation(
                    pitch=tf.rotation.pitch + m.pitch,
                    yaw=tf.rotation.yaw + m.yaw,
                    roll=0.0,
                )
            else:
                cam_loc = self._carla.Location(
                    x=loc.x - fwd.x * 8.0,
                    y=loc.y - fwd.y * 8.0,
                    z=loc.z + 4.0,
                )
                rot = self._carla.Rotation(
                    pitch=-15.0, yaw=tf.rotation.yaw, roll=0.0
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
