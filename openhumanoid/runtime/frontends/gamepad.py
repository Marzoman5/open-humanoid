"""Gamepad front end (R9): a mapping from sticks and buttons to Command API v1 messages. Works with no network (R8: a handheld controller).

Layout (Xbox / generic SDL layout; remap in `GamepadMap`):

| input                | command |
|----------------------|---------|
| hold LB (dead-man)   | enables walking: sticks are ignored while it is released and the robot is told to stop |
| left stick           | velocity: up = forward (vx), left/right = strafe (vy) |
| right stick X        | turn (wz) |
| A / B / X / Y        | stand / wave / dance / pickup |
| D-pad                | look-at: left/right/up/down (neck + waist); D-pad centre keeps the last look direction; RB resets it |
| Back (hold 0.5 s)    | e-stop |
| Start                | reset e-stop (only accepted when the robot is still) |

`GamepadMapper.update(state, now)` is pure (state in, messages out) so it is tested with scripted `PadState`s. `PygamePad` reads a real
controller through pygame (optional dependency, imported lazily).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

API_V = 1


@dataclass
class PadState:
    axes: dict = field(default_factory=dict)          # lx, ly, rx, ry in [-1, 1]; ly negative = stick pushed up (SDL convention)
    buttons: set = field(default_factory=set)         # names: A B X Y LB RB BACK START
    hat: tuple = (0, 0)                               # d-pad (x, y), y = +1 up


@dataclass
class GamepadMap:
    deadzone: float = 0.14
    vmax: tuple = (0.15, 0.07, 0.5)                   # slightly below the planner limits
    ttl: float = 0.4
    estop_hold_s: float = 0.5
    look_range: tuple = (1.0, 0.45)                   # yaw, pitch of the look-at point per d-pad press (rad), applied at 1 m


class GamepadMapper:
    def __init__(self, cfg: GamepadMap | None = None):
        self.cfg = cfg or GamepadMap()
        self.prev: set = set()
        self.back_t: float | None = None
        self.walking = False
        self.look = [0.0, 0.0]
        self.rate_t = 0.0

    def _dz(self, v: float) -> float:
        d = self.cfg.deadzone
        if abs(v) < d:
            return 0.0
        return (abs(v) - d) / (1 - d) * (1 if v > 0 else -1)

    def update(self, st: PadState, now: float | None = None) -> list:
        now = time.monotonic() if now is None else now
        c = self.cfg
        out: list = []
        pressed = st.buttons - self.prev
        # --- e-stop: hold BACK
        if "BACK" in st.buttons:
            if self.back_t is None:
                self.back_t = now
            elif now - self.back_t >= c.estop_hold_s:
                out.append({"v": API_V, "cmd": "estop", "reason": "gamepad"})
                self.back_t = now + 1e9
        else:
            self.back_t = None
        if "START" in pressed:
            out.append({"v": API_V, "cmd": "reset_estop"})
        # --- velocity under dead-man
        if "LB" in st.buttons:
            vx = -self._dz(st.axes.get("ly", 0.0)) * c.vmax[0]
            vy = -self._dz(st.axes.get("lx", 0.0)) * c.vmax[1]
            wz = -self._dz(st.axes.get("rx", 0.0)) * c.vmax[2]
            out.append({"v": API_V, "cmd": "velocity", "vx": round(vx, 4), "vy": round(vy, 4), "wz": round(wz, 4), "ttl": c.ttl})
            self.walking = True
        elif self.walking:
            out.append({"v": API_V, "cmd": "velocity", "vx": 0.0, "vy": 0.0, "wz": 0.0, "ttl": c.ttl})
            self.walking = False
        # --- behaviours
        for b, name in (("A", "stand"), ("B", "wave"), ("X", "dance"), ("Y", "pickup")):
            if b in pressed:
                out.append({"v": API_V, "cmd": "behaviour", "name": name, "params": {}})
        # --- look-at via d-pad
        if st.hat != (0, 0) or "RB" in pressed:
            if "RB" in pressed:
                self.look = [0.0, 0.0]
                out.append({"v": API_V, "cmd": "look_at", "target": None})
            else:
                self.look[0] = max(-1.0, min(1.0, self.look[0] - st.hat[0] * 0.5))
                self.look[1] = max(-1.0, min(1.0, self.look[1] + st.hat[1] * 0.5))
                yaw, pitch = self.look[0] * c.look_range[0], self.look[1] * c.look_range[1]
                import math
                x = 1.0
                out.append({"v": API_V, "cmd": "look_at", "target": [x, math.tan(yaw), 0.0 + math.tan(pitch)]})
        self.prev = set(st.buttons)
        return out


class PygamePad:
    """Reads the first connected controller with pygame (pip install pygame). Not used by the tests."""

    BUTTONS = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "BACK", 7: "START"}

    def __init__(self):
        import pygame  # type: ignore
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("no gamepad connected")
        self.js = pygame.joystick.Joystick(0)
        self.js.init()
        self.pg = pygame

    def read(self) -> PadState:
        self.pg.event.pump()
        ax = {"lx": self.js.get_axis(0), "ly": self.js.get_axis(1), "rx": self.js.get_axis(3 if self.js.get_numaxes() > 3 else 2),
              "ry": self.js.get_axis(4 if self.js.get_numaxes() > 4 else 3)}
        btn = {n for i, n in self.BUTTONS.items() if i < self.js.get_numbuttons() and self.js.get_button(i)}
        hat = self.js.get_hat(0) if self.js.get_numhats() else (0, 0)
        return PadState(ax, btn, hat)


def run_gamepad(client, rate_hz: float = 30.0, pad=None) -> None:     # pragma: no cover - needs hardware
    pad = pad or PygamePad()
    mapper = GamepadMapper()
    while True:
        for msg in mapper.update(pad.read()):
            client.bus.submit(msg, source="gamepad")
        time.sleep(1.0 / rate_hz)
