"""Command API v1: the one interface every front end (gamepad, phone web UI, scripts, a later LLM/MCP plugin) uses to drive the robot.

Messages are JSON objects (`dict`s in Python). Every request has `"v": 1` and `"cmd"`; an optional `"id"` is echoed in the reply.
Replies: `{"v": 1, "id": ..., "ok": true, "result": {...}}` or `{"v": 1, "id": ..., "ok": false, "error": {"code": "...", "message": "..."}}`.

| cmd          | fields                                                        | effect |
|--------------|---------------------------------------------------------------|--------|
| velocity     | vx, vy [m/s], wz [rad/s], ttl [s, default 0.5]                | walk; expires after `ttl` without a refresh (dead-man) |
| stop         | name (optional: wave, dance, pickup, walk, look_at, pose)     | stop that behaviour (none: everything, back to stand) |
| behaviour    | name: stand|walk|wave|dance|pickup, params {...}              | start a behaviour (wave: side; dance: n_phrases, bpm; pickup: table_height_m) |
| pose         | joints {name: rad}                                            | upper-body joint targets (neck, waist, arms); legs are refused |
| look_at      | target [x, y, z] in the body frame (x forward, y left, z up, metres from the floor) or null | neck + waist turn toward it |
| estop        | reason (optional)                                             | latch the e-stop (torque off) |
| reset_estop  |                                                               | clear it (only when the robot is still); comes back limp |
| enable       |                                                               | leave limp and stand up from the crouch pose is NOT implemented: enables torque only when upright |
| status       |                                                               | battery, safety state, behaviour, tilt, joint temperatures |
| describe     |                                                               | this table as data (for tool-schema generation) |

Thread safety: `CommandBus.submit()` may be called from any thread; actions are queued and executed by the control loop between cycles.
Nothing here talks to the HAL: the safety layer sits between the commands and the servos.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass

API_VERSION = 1

COMMANDS = {
    "velocity": {"fields": {"vx": "m/s forward", "vy": "m/s left", "wz": "rad/s counter-clockwise", "ttl": "seconds (default 0.5)"},
                 "limits": {"vx": [-0.16, 0.16], "vy": [-0.08, 0.08], "wz": [-0.6, 0.6]}},
    "stop": {"fields": {"name": "optional behaviour name"}},
    "behaviour": {"fields": {"name": "stand|walk|wave|dance|pickup", "params": "object"}},
    "pose": {"fields": {"joints": "object name -> radians (upper body only)"}},
    "look_at": {"fields": {"target": "[x, y, z] metres in the body frame, or null"}},
    "estop": {"fields": {"reason": "string"}},
    "reset_estop": {"fields": {}},
    "enable": {"fields": {}},
    "status": {"fields": {}},
    "describe": {"fields": {}},
}
ACTIONS = {"velocity", "stop", "behaviour", "pose", "look_at", "estop", "reset_estop", "enable"}
BEHAVIOURS = ("stand", "walk", "wave", "dance", "pickup")


def error(code: str, message: str, rid=None) -> dict:
    return {"v": API_VERSION, "id": rid, "ok": False, "error": {"code": code, "message": message}}


def ok(result: dict, rid=None) -> dict:
    return {"v": API_VERSION, "id": rid, "ok": True, "result": result}


def validate(msg: dict) -> str | None:
    """Return an error message or None."""
    if not isinstance(msg, dict):
        return "message must be a JSON object"
    if msg.get("v", API_VERSION) != API_VERSION:
        return f"unsupported api version {msg.get('v')} (this is {API_VERSION})"
    cmd = msg.get("cmd")
    if cmd not in COMMANDS:
        return f"unknown cmd {cmd!r}; known: {sorted(COMMANDS)}"
    try:
        if cmd == "velocity":
            for k in ("vx", "vy", "wz"):
                float(msg.get(k, 0.0))
            if float(msg.get("ttl", 0.5)) <= 0:
                return "ttl must be positive"
        elif cmd == "behaviour":
            if msg.get("name") not in BEHAVIOURS:
                return f"name must be one of {BEHAVIOURS}"
            if not isinstance(msg.get("params", {}), dict):
                return "params must be an object"
        elif cmd == "pose":
            j = msg.get("joints")
            if not isinstance(j, dict) or not j:
                return "joints must be a non-empty object"
            for k, v in j.items():
                float(v)
        elif cmd == "look_at":
            t = msg.get("target")
            if t is not None and (len(t) != 3 or any(not isinstance(float(x), float) for x in t)):
                return "target must be [x, y, z] or null"
    except (TypeError, ValueError) as e:
        return f"bad field: {e}"
    return None


@dataclass
class Pending:
    msg: dict
    t: float


class CommandBus:
    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self.status_snapshot: dict = {}
        self.sources: dict = {}
        self.log: list = []

    def set_status(self, st: dict) -> None:
        with self._lock:
            self.status_snapshot = st

    def submit(self, msg, source: str = "api") -> dict:
        if isinstance(msg, (str, bytes)):
            try:
                msg = json.loads(msg)
            except json.JSONDecodeError as e:
                return error("bad_json", str(e))
        rid = msg.get("id") if isinstance(msg, dict) else None
        err = validate(msg)
        if err:
            return error("invalid", err, rid)
        cmd = msg["cmd"]
        if cmd == "status":
            with self._lock:
                return ok(dict(self.status_snapshot), rid)
        if cmd == "describe":
            return ok({"api_version": API_VERSION, "commands": COMMANDS, "behaviours": list(BEHAVIOURS)}, rid)
        if cmd == "estop":                       # the e-stop jumps the queue: it is consumed by the runtime before anything else
            self._q.put(Pending({**msg, "_source": source}, time.monotonic()))
            return ok({"queued": True}, rid)
        self._q.put(Pending({**msg, "_source": source}, time.monotonic()))
        return ok({"queued": True}, rid)

    def drain(self) -> list:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        out.sort(key=lambda p: 0 if p.msg["cmd"] == "estop" else 1)
        return out


class RobotClient:
    """Convenience wrapper over a CommandBus (in-process) with the same verbs as the JSON API. A TCP/HTTP client would expose the same methods."""

    def __init__(self, bus: CommandBus, source: str = "python"):
        self.bus = bus
        self.source = source

    def _send(self, **kw) -> dict:
        return self.bus.submit({"v": API_VERSION, **kw}, self.source)

    def velocity(self, vx=0.0, vy=0.0, wz=0.0, ttl=0.5):
        return self._send(cmd="velocity", vx=vx, vy=vy, wz=wz, ttl=ttl)

    def behaviour(self, name, **params):
        return self._send(cmd="behaviour", name=name, params=params)

    def stop(self, name=None):
        return self._send(cmd="stop", name=name)

    def pose(self, **joints):
        return self._send(cmd="pose", joints=joints)

    def look_at(self, x, y, z):
        return self._send(cmd="look_at", target=[x, y, z])

    def stop_looking(self):
        return self._send(cmd="look_at", target=None)

    def estop(self, reason="client"):
        return self._send(cmd="estop", reason=reason)

    def reset_estop(self):
        return self._send(cmd="reset_estop")

    def status(self):
        return self._send(cmd="status")
