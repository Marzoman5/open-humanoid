"""Open Duck Mini's own reference motion, decoded at run time from a scratch copy (never stored in the repository).

See `calibration.py` for the licence note: ODM's Playground / reference-motion repositories have NO LICENSE, so this module reads the
caller's scratch folder, keeps nothing and publishes only derived numbers. The pickle format is the one written by ODM's own
`scripts/fit_poly.py` (visible in its output): a dict `{ "dx_dy_dtheta": {"coefficients": {"dim_i": [c0..c15]}, "period", "fps", ...} }`.
"""
from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np

from .calibration import ExternalRobot, LEG_BASES, pickle_is_numpy_only
from .kin import Reference, quat_from_yaw_pitch


class OdmPoly:
    """Per-command polynomial reference: 40 polynomials of degree 15 in the gait phase t in [0, 1]: 16 joint positions, 16 joint
    velocities, 2 foot contacts, base linear velocity (3) and base angular velocity (3). A command is snapped to the nearest tabulated
    one exactly like ODM's training code does (so a 'straight' command lands on the tabulated dy = -0.037, dtheta = -0.074 entry)."""

    def __init__(self, path):
        ok, seen = pickle_is_numpy_only(Path(path))
        if not ok:
            raise ValueError(f"refusing to unpickle {path}: unexpected globals {seen}")
        with open(path, "rb") as f:
            data = pickle.load(f)               # only numpy dtype / scalar opcodes, verified above
        self.coef = {}
        first = next(iter(data.values()))
        self.period = float(first["period"])
        self.fps = int(first["fps"])
        self.startend_double_support_ratio = float(first["startend_double_support_ratio"])
        for name, v in data.items():
            dx, dy, dth = (float(x) for x in name.split("_"))
            self.coef[(dx, dy, dth)] = np.array([v["coefficients"][f"dim_{i}"] for i in range(40)], dtype=float)   # ascending powers
        self.dxs = sorted({k[0] for k in self.coef})
        self.dys = sorted({k[1] for k in self.coef})
        self.dths = sorted({k[2] for k in self.coef})

    def snap(self, dx: float, dy: float, dth: float):
        dx = float(np.clip(dx, self.dxs[0], self.dxs[-1]))
        dy = float(np.clip(dy, self.dys[0], self.dys[-1]))
        dth = float(np.clip(dth, self.dths[0], self.dths[-1]))
        return (self.dxs[int(np.argmin(np.abs(np.array(self.dxs) - dx)))], self.dys[int(np.argmin(np.abs(np.array(self.dys) - dy)))],
                self.dths[int(np.argmin(np.abs(np.array(self.dths) - dth)))])

    def frames(self, key, phase: np.ndarray) -> np.ndarray:
        c = self.coef[key]                                                          # (40, 16)
        t = np.clip(phase, 0.0, 1.0)
        pw = t[:, None] ** np.arange(c.shape[1])[None, :]
        return pw @ c.T                                                             # (T, 40)


def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class OdmGround:
    """FK helper on ODM's model: sole normals and lowest sole points, to put a joint-space reference on the floor."""

    def __init__(self, robot: ExternalRobot):
        import mujoco
        self.mj = mujoco
        self.robot = robot
        self.m = robot.model
        self.d = mujoco.MjData(self.m)
        self.qadr = np.array([self.m.joint(n).qposadr[0] for n in robot.names])
        self.gid = {s: self.m.geom(f"{'left' if s == 'l' else 'right'}_foot_bottom_tpu").id for s in "lr"}
        self.verts, self.nloc = {}, {}
        mujoco.mj_resetDataKeyframe(self.m, self.d, 0)
        mujoco.mj_forward(self.m, self.d)
        for s, g in self.gid.items():
            mid = self.m.geom_dataid[g]
            v = self.m.mesh_vert[self.m.mesh_vertadr[mid]:self.m.mesh_vertadr[mid] + self.m.mesh_vertnum[mid]].copy()
            self.verts[s] = v
            w = v - v.mean(0)
            _, evec = np.linalg.eigh(w.T @ w)
            n = evec[:, 0]
            Rg = self.d.geom_xmat[g].reshape(3, 3)
            if (Rg @ n)[2] < 0:                  # sole normal in the geom frame, pointing up when the foot stands in the home pose
                n = -n
            self.nloc[s] = n

    def home_q(self) -> np.ndarray:
        self.mj.mj_resetDataKeyframe(self.m, self.d, 0)
        return self.d.qpos[self.qadr].copy()

    def set_q(self, q):
        self.d.qpos[:7] = [0, 0, 0, 1, 0, 0, 0]
        self.d.qpos[self.qadr] = q
        self.mj.mj_kinematics(self.m, self.d)

    def sole_pitch(self, s) -> float:
        """Base pitch (rotation about y) that makes foot `s` flat, for the joints set by set_q."""
        Rg = self.d.geom_xmat[self.gid[s]].reshape(3, 3)
        m = Rg @ self.nloc[s]
        return -math.atan2(m[0], m[2])

    def lowest_z(self, s, pitch: float) -> float:
        Rg = self.d.geom_xmat[self.gid[s]].reshape(3, 3)
        w = self.verts[s] @ Rg.T + self.d.geom_xpos[self.gid[s]]
        return float((w @ _rot_y(pitch).T)[:, 2].min())


def odm_reference(robot: ExternalRobot, poly: OdmPoly, command=(0.148, 0.0, 0.0), n_periods: int = 10, lead_s: float = 0.0, dt: float = 0.01) -> Reference:
    """ODM's own gait (a command snapped to the table) as a Reference: joints from the polynomials, base x-y integrated from the reference base
    velocity, base pitch from the flatness of the soles in contact, base height from the floor. Starts from ODM's home pose over `lead_s`."""
    key = poly.snap(*command)
    gnd = OdmGround(robot)
    names = robot.names
    ix = {n: i for i, n in enumerate(names)}
    nper = int(round(n_periods * poly.period / dt))
    t = np.arange(nper) * dt
    fr = poly.frames(key, (t / poly.period) % 1.0)
    q = np.zeros((nper, len(names)))
    for k, bn in enumerate(LEG_BASES):                 # ODM reference order: left leg 0-4, head joints, right leg 11-15
        q[:, ix[f"{bn}_l"]] = fr[:, k]
        q[:, ix[f"{bn}_r"]] = fr[:, 11 + k]
    q[:, ix["neck_pitch"]], q[:, ix["head_pitch"]], q[:, ix["head_yaw"]] = fr[:, 5], fr[:, 6], fr[:, 7]
    contacts = fr[:, 32:34] > 0.5
    vel = fr[:, 34:37]
    q_home = gnd.home_q()
    n_lead = int(round(lead_s / dt))
    s = np.clip(np.arange(n_lead) / max(n_lead - 1, 1), 0, 1)
    s = s ** 3 * (10 - 15 * s + 6 * s * s)
    Q = np.concatenate([q_home[None, :] * (1 - s[:, None]) + q[0][None, :] * s[:, None], q])
    C = np.concatenate([np.ones((n_lead, 2), bool), contacts])
    V = np.concatenate([np.zeros((n_lead, 3)), vel])
    T = len(Q)
    pos, quat, pitch = np.zeros((T, 3)), np.zeros((T, 4)), np.zeros(T)
    for i in range(T):
        gnd.set_q(Q[i])
        th = [gnd.sole_pitch(s_) for s_, c_ in zip("lr", C[i]) if c_]
        pitch[i] = float(np.mean(th)) if th else float(np.mean([gnd.sole_pitch("l"), gnd.sole_pitch("r")]))
    pitch = np.convolve(np.pad(pitch, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid")      # the contact flags switch: smooth the pitch a little
    for i in range(T):
        gnd.set_q(Q[i])
        zs = [gnd.lowest_z(s_, pitch[i]) for s_, c_ in zip("lr", C[i]) if c_] or [gnd.lowest_z("l", pitch[i]), gnd.lowest_z("r", pitch[i])]
        pos[i, 2] = -min(zs)
        quat[i] = quat_from_yaw_pitch(0.0, pitch[i])[0]
    xy = np.cumsum(V[:, :2], axis=0) * dt
    pos[:, :2] = xy - xy[0]
    ref = Reference(f"odm_own_{key[0]:+.3f}_{key[1]:+.3f}_{key[2]:+.3f}", dt, Q, pos, quat, True,
                    [f"ODM own reference, command snapped to dx={key[0]}, dy={key[1]}, dtheta={key[2]}"],
                    {"command": list(command), "table_key": list(key), "period_s": poly.period, "mean_speed_mps": float(np.linalg.norm(vel[:, :2].mean(0))),
                     "n_periods": n_periods, "walk_window": [(n_lead + int(round(2 * poly.period / dt))) * dt, (T - 1) * dt]})
    ref.stance = C
    return ref
