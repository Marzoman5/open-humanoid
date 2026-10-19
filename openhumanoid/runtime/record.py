"""Record a runtime scenario as a GIF (or MP4 if imageio-ffmpeg is installed).

Frames come from the same SimHAL physics the scenario tests run. Nothing is staged:
the recorder only wraps `SimHAL.tick` and renders the current MuJoCo state at a fixed
frame rate. The scenario's own pass/fail result is printed alongside, so a video is
never shown without its verdict.

    python -m openhumanoid.runtime.record dance docs/media/adam_dance.gif
    python -m openhumanoid.runtime.record walk_and_turn docs/media/adam_walk.gif --fps 15
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from . import scenarios

SCENARIOS = {
    "stand": lambda: scenarios.stand(seconds=8.0),
    "walk_and_turn": lambda: scenarios.walk_and_turn(),
    "wave": lambda: scenarios.wave(),
    "dance": lambda: scenarios.dance(),
    "pickup": lambda: scenarios.pickup(),
    "push_stand_fwd": lambda: scenarios.push_stand(direction="fwd"),
    "push_walk_left": lambda: scenarios.push_walk(direction="left"),
}


def record(name: str, out: Path, fps: int = 15, width: int = 480, height: int = 360, max_s: float = 60.0) -> dict:
    frames: list[np.ndarray] = []
    orig_make_sim = scenarios.make_sim

    def make_sim_recording(*a, **kw):
        rt, hal = orig_make_sim(*a, **kw)
        renderer = mujoco.Renderer(hal.mjm, height, width)
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.distance, cam.elevation, cam.azimuth = 1.05, -10.0, 135.0
        state = {"next_t": hal.t}
        orig_tick = hal.tick

        def tick():
            orig_tick()
            if hal.t >= state["next_t"] and hal.t <= max_s:
                cam.lookat[:] = hal.data.qpos[:3] + np.array([0.0, 0.0, -0.05])
                renderer.update_scene(hal.data, camera=cam)
                frames.append(renderer.render().copy())
                state["next_t"] += 1.0 / fps

        hal.tick = tick
        return rt, hal

    scenarios.make_sim = make_sim_recording
    try:
        result = SCENARIOS[name]()
    finally:
        scenarios.make_sim = orig_make_sim
    out.parent.mkdir(parents=True, exist_ok=True)
    import imageio.v2 as imageio
    if out.suffix.lower() == ".mp4":
        imageio.mimsave(out, frames, fps=fps)
    else:
        imageio.mimsave(out, frames, duration=1000.0 / fps, loop=0)
    verdict = {"scenario": name, "frames": len(frames), "file": str(out),
               "result": getattr(result, "__dict__", str(result))}
    return verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openhumanoid.runtime.record")
    ap.add_argument("scenario", choices=sorted(SCENARIOS))
    ap.add_argument("out", type=Path)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--height", type=int, default=360)
    a = ap.parse_args(argv)
    v = record(a.scenario, a.out, a.fps, a.width, a.height)
    print(json.dumps(v, indent=1, default=str)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
