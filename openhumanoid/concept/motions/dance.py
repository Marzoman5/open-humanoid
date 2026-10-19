"""A 30-60 s scripted dance (double support): keyframed arms, waist/neck, weight shift and knee bounce.

Choreography = 8 phrases of 8 beats at 92 BPM (~41 s). Arm poses are named keyframes (shoulder pitch/roll, elbow, left-arm
convention, the right arm is mirrored). Upper-body series are passed through the velocity-limited QP smoother, so the
dance never asks an actuator for more speed than `v_limit_frac` of its no-load speed. The legs follow by IK with the
whole-body COM kept over the feet (sway moves the COM target inside the support polygon).
"""
from __future__ import annotations

import math

import numpy as np

from ..kin import RobotKin, smoothstep5
from .common import GRIP_CLOSED, knee_flex_from, rest_upper_body
from .posture import double_support
from .smoothing import smooth_series

D = math.radians
POSES = {   # (shoulder_pitch, shoulder_roll, elbow) degrees, left arm; right arm uses roll -> -roll
    "rest": (0, 8, -20), "fwd": (-90, 10, -30), "side": (0, 90, -20), "hi5": (-50, 105, -50), "cross": (-60, 5, -110),
    "hip": (25, 25, -100), "vee": (-20, 140, -10), "point": (-90, 35, -5), "clap": (-80, 5, -95), "low": (10, 40, -10),
}


def kf(tau: np.ndarray, times, values) -> np.ndarray:
    """Smoothstep interpolation through keyframes (times in beats, any number of columns in values)."""
    times = np.asarray(times, float)
    values = np.asarray(values, float)
    out = np.zeros((len(tau),) + values.shape[1:])
    for i, t in enumerate(tau):
        j = int(np.clip(np.searchsorted(times, t, side="right") - 1, 0, len(times) - 2))
        s = smoothstep5((t - times[j]) / max(times[j + 1] - times[j], 1e-9))
        out[i] = values[j] + (values[j + 1] - values[j]) * s
    return out


def choreography(n_phrases: int = 8):
    """Per phrase: arm keyframes {side: [(beat, pose_name)]}, waist/neck/sway/bounce functions of the beat."""
    S = {
        0: dict(l=[(0, "rest"), (3, "fwd"), (5, "fwd"), (8, "side")], r=[(0, "rest"), (3, "fwd"), (5, "fwd"), (8, "side")],
                waist=lambda b: 0 * b, neck=lambda b: D(25) * np.sin(math.pi * b / 2), sway=lambda b: 0 * b,
                bounce=lambda b: D(6) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        1: dict(l=[(0, "side"), (2, "hi5"), (4, "side"), (6, "hi5"), (8, "side")], r=[(0, "side"), (2, "side"), (4, "hi5"), (6, "side"), (8, "side")],
                waist=lambda b: D(10) * np.sin(math.pi * b / 2), neck=lambda b: D(20) * np.sin(math.pi * b / 2),
                sway=lambda b: np.sin(math.pi * b / 2), bounce=lambda b: D(4) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        2: dict(l=[(0, "side"), (2, "cross"), (4, "side"), (6, "cross"), (8, "hip")], r=[(0, "side"), (2, "side"), (4, "cross"), (6, "side"), (8, "hip")],
                waist=lambda b: D(35) * np.sin(math.pi * b / 2), neck=lambda b: -D(30) * np.sin(math.pi * b / 2),
                sway=lambda b: 0.6 * np.sin(math.pi * b / 2), bounce=lambda b: D(5) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        3: dict(l=[(0, "hip"), (1, "vee"), (2, "hip"), (3, "vee"), (4, "hip"), (5, "vee"), (6, "hip"), (7, "vee"), (8, "hip")],
                r=[(0, "hip"), (1, "vee"), (2, "hip"), (3, "vee"), (4, "hip"), (5, "vee"), (6, "hip"), (7, "vee"), (8, "hip")],
                waist=lambda b: 0 * b, neck=lambda b: D(15) * np.sin(math.pi * b), sway=lambda b: 0 * b,
                bounce=lambda b: D(22) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        4: dict(l=[(0, "hip"), (8, "hip")], r=[(0, "hip"), (1.5, "hi5"), (8, "hi5")],
                waist=lambda b: -D(12) * np.sin(math.pi * b / 4), neck=lambda b: -D(30) * np.sin(math.pi * b / 4),
                sway=lambda b: 0.5 * np.sin(math.pi * b / 2), bounce=lambda b: D(4) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        5: dict(l=[(0, "hip"), (2, "point"), (4, "hip"), (6, "low"), (8, "side")], r=[(0, "hip"), (2, "hip"), (4, "point"), (6, "low"), (8, "side")],
                waist=lambda b: D(25) * np.sin(math.pi * b / 2), neck=lambda b: D(40) * np.sin(math.pi * b / 2),
                sway=lambda b: 0.7 * np.sin(math.pi * b / 2), bounce=lambda b: D(8) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        6: dict(l=[(0, "side"), (1, "clap"), (2, "side"), (3, "clap"), (4, "fwd"), (6, "vee"), (8, "side")],
                r=[(0, "side"), (1, "clap"), (2, "side"), (3, "clap"), (4, "fwd"), (6, "vee"), (8, "side")],
                waist=lambda b: D(20) * np.sin(math.pi * b / 2), neck=lambda b: D(25) * np.sin(math.pi * b / 2),
                sway=lambda b: 0.6 * np.sin(math.pi * b / 2), bounce=lambda b: D(10) * (0.5 - 0.5 * np.cos(2 * math.pi * b))),
        7: dict(l=[(0, "side"), (4, "vee"), (8, "rest")], r=[(0, "side"), (4, "vee"), (8, "rest")],
                waist=lambda b: 0 * b, neck=lambda b: 0 * b, sway=lambda b: 0 * b,
                bounce=lambda b: D(35) * np.sin(math.pi * np.clip(b, 0, 8) / 8) ** 2),
    }
    return [S[i % 8] for i in range(n_phrases)]


def dance(kin: RobotKin, dt: float = 0.01, bpm: float = 92.0, n_phrases: int = 8, v_limit: dict | None = None) -> Reference:
    """v_limit: {joint name: max speed rad/s} from the actuators (None -> 3 rad/s everywhere)."""
    tb = 60.0 / bpm
    beats_total = 8 * n_phrases
    lead_in, lead_out = 1.0, 1.5
    T = int((beats_total * tb + lead_in + lead_out) / dt) + 1
    t = np.arange(T) * dt
    beat = np.clip((t - lead_in) / tb, 0, beats_total)
    in_dance = ((t >= lead_in) & (t <= lead_in + beats_total * tb)).astype(float)
    f0 = knee_flex_from(kin)
    lg = kin.lg
    phrases = choreography(n_phrases)
    up = {n: np.zeros(T) for n in kin.names}
    rest = rest_upper_body(kin, 1)[0]
    for n in kin.names:
        up[n] = np.full(T, rest[kin.index[n]])
    waist = np.zeros(T)
    neck = np.zeros(T)
    sway = np.zeros(T)
    bounce = np.zeros(T)
    for ip, ph in enumerate(phrases):
        m = (beat >= ip * 8) & (beat < (ip + 1) * 8 + (1e-9 if ip == n_phrases - 1 else 0)) & (in_dance > 0)
        if not m.any():
            continue
        b = beat[m] - ip * 8
        waist[m], neck[m], sway[m], bounce[m] = ph["waist"](b), ph["neck"](b), ph["sway"](b), ph["bounce"](b)
        for side, sgn in (("l", 1.0), ("r", -1.0)):
            keys = ph[side]
            times = [k[0] for k in keys]
            vals = np.array([[D(POSES[k[1]][0]), sgn * D(POSES[k[1]][1]), D(POSES[k[1]][2])] for k in keys])
            ser = kf(b, times, vals)
            for c, base in enumerate(("shoulder_pitch", "shoulder_roll", "elbow")):
                if kin.has(f"{base}_{side}"):
                    up[f"{base}_{side}"][m] = ser[:, c]
    # blend the rest posture in/out of the dance
    edge = smoothstep5(np.clip((t - lead_in + 0.0) / 0.8, 0, 1)) * smoothstep5(np.clip((lead_in + beats_total * tb + lead_out - 0.5 - t) / 0.8, 0, 1))
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        for c, base in enumerate(("shoulder_pitch", "shoulder_roll", "elbow")):
            n = f"{base}_{side}"
            if kin.has(n):
                r0 = rest[kin.index[n]]
                up[n] = r0 + (up[n] - r0) * np.maximum(edge, in_dance * 0 + edge)
    if kin.has("waist_yaw"):
        up["waist_yaw"] = waist * edge
    if kin.has("neck_yaw"):
        up["neck_yaw"] = neck * edge
    # velocity-limited smoothing of every moving upper-body joint
    smoothed = {}
    notes = []
    for j in kin.robot.joints:
        n = j["name"]
        if n not in kin.index or n.startswith(("hip", "knee", "ankle")) or j["base"] == "gripper":
            continue
        series = up.get(n)
        if series is None or np.ptp(series) < 1e-6:
            continue
        lo, hi = D(j["range"][0]), D(j["range"][1])
        vmax = (v_limit or {}).get(n, 3.0)
        smoothed[n] = smooth_series(series, dt, vmax, lo, hi)
        dev = float(np.abs(smoothed[n] - series).max())
        if dev > D(8):
            notes.append(f"{n}: smoother deviates {math.degrees(dev):.0f} deg from the choreography (speed/range limits)")
    up.update(smoothed)
    for s in ("l", "r"):
        if kin.has(f"gripper_{s}"):
            up[f"gripper_{s}"] = np.full(T, GRIP_CLOSED)
    # the per-phrase functions are not continuous across phrase boundaries: smooth sway and bounce as well
    sway = smooth_series(sway, dt, 1.2, -1.0, 1.0, lam=2e-3)
    bounce = smooth_series(bounce, dt, 1.0, 0.0, D(60), lam=2e-3)
    flex = f0 + bounce * edge
    hy = lg.hip_y
    com_xy = np.stack([np.full(T, lg.foot_off), 0.5 * hy * sway * edge], 1)
    ref = double_support(kin, "dance", dt, T, flex=flex, com_xy=com_xy, upper=up, notes=notes,
                         meta={"bpm": bpm, "beats": beats_total, "duration_s": T * dt, "phrases": n_phrases,
                               "smoother": "casadi QP (osqp)" if __import__("openhumanoid.concept.motions.smoothing", fromlist=["x"]).have_casadi() else "moving average (casadi missing)"})
    return ref
