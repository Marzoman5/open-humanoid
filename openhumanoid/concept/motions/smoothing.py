"""Velocity-limited smoothing of keyframed joint series.

Where casadi adds value: a QP per joint that follows the choreography as closely as the actuator's speed and the joint
range allow, with a minimum-acceleration penalty (no velocity kinks, no ringing from stiff keyframes). If casadi is not
installed the fallback is a moving-average filter plus a velocity clip, which is cruder (it can leave the keyframe
envelope) but keeps the module usable with only the core dependencies.
"""
from __future__ import annotations

import numpy as np

try:  # optional extra: pip install "openhumanoid[concept]"
    import casadi as ca
except Exception:  # noqa: BLE001
    ca = None


def have_casadi() -> bool:
    return ca is not None


def smooth_series(q_des: np.ndarray, dt: float, vmax: float, lo: float, hi: float, lam: float = 5e-4,
                  amax: float | None = None) -> np.ndarray:
    """min sum (q - q_des)^2 + lam/dt^4 * sum (second difference)^2  s.t. |dq/dt| <= vmax, lo <= q <= hi, q[0], q[-1] fixed."""
    q_des = np.asarray(q_des, float)
    T = len(q_des)
    if np.ptp(q_des) < 1e-9:
        return q_des.copy()
    if ca is None:
        k = max(3, int(0.15 / dt) | 1)
        ker = np.ones(k) / k
        pad = np.pad(q_des, (k // 2, k // 2), mode="edge")
        y = np.convolve(pad, ker, mode="valid")
        y = np.clip(y, lo, hi)
        out = y.copy()
        step = vmax * dt
        for i in range(1, T):
            out[i] = np.clip(out[i], out[i - 1] - step, out[i - 1] + step)
        return out
    q = ca.SX.sym("q", T)
    d2 = q[2:] - 2 * q[1:-1] + q[:-2]
    f = ca.sumsqr(q - q_des) + lam / dt ** 4 * ca.sumsqr(d2) * dt ** 2
    g = [q[1:] - q[:-1]]
    lbg, ubg = [-vmax * dt] * (T - 1), [vmax * dt] * (T - 1)
    if amax is not None:
        g.append(d2)
        lbg += [-amax * dt * dt] * (T - 2)
        ubg += [amax * dt * dt] * (T - 2)
    lbx = np.full(T, lo)
    ubx = np.full(T, hi)
    q0 = float(np.clip(q_des[0], lo, hi))
    q1 = float(np.clip(q_des[-1], lo, hi))
    lbx[0] = ubx[0] = q0
    lbx[-1] = ubx[-1] = q1
    prob = {"x": q, "f": f, "g": ca.vertcat(*g)}
    for plugin in ("osqp", "qrqp", "highs"):
        try:
            solver = ca.qpsol("s", plugin, prob, {"print_time": 0, "osqp": {"verbose": False}} if plugin == "osqp" else {"print_time": 0})
            sol = solver(x0=np.clip(q_des, lo, hi), lbx=lbx, ubx=ubx, lbg=lbg, ubg=ubg)
            return np.array(sol["x"]).ravel()
        except Exception:  # noqa: BLE001
            continue
    return smooth_series.__wrapped_fallback__(q_des, dt, vmax, lo, hi)  # pragma: no cover


def _fallback(q_des, dt, vmax, lo, hi):  # pragma: no cover
    out = np.clip(q_des, lo, hi).copy()
    step = vmax * dt
    for i in range(1, len(out)):
        out[i] = np.clip(out[i], out[i - 1] - step, out[i - 1] + step)
    return out


smooth_series.__wrapped_fallback__ = _fallback
