"""The frozen gait on an imported MJCF (Open Duck Mini's own model): numerical leg IK so the template's walk / stand / squat generators
(`motions/`) can drive a robot whose legs are not the template's (5 joints, lateral offsets between the roll and the pitch axes, mirrored joint
signs). See `calibration.py` for the licence note: only ODM's MJCF is read, at run time, from a scratch folder."""
from __future__ import annotations

import math

import numpy as np

from .calibration import ExternalRobot, LEG_BASES
from .kin import LegGeom, RobotKin, quat_from_yaw_pitch


class ExternalKin(RobotKin):
    """RobotKin for an ExternalRobot: MuJoCo FK/COM as usual, legs by damped-least-squares IK on the real kinematic chain."""

    def __init__(self, robot: ExternalRobot):
        super().__init__(robot, robot.build_model())
        f = robot.facts
        self.lg = LegGeom(f["L1"], f["L2"], f["foot_y_plan"], 0.0, f["ankle_h"], f["foot_len"], f["foot_w"], f["foot_off"])
        mj, m = self.mj, self.model
        self.d_ik = mj.MjData(m)
        self.lq = {s: np.array([m.joint(f"{b}_{s}").qposadr[0] for b in LEG_BASES]) for s in "lr"}
        self.ld = {s: np.array([m.joint(f"{b}_{s}").dofadr[0] for b in LEG_BASES]) for s in "lr"}
        self.lrange = {s: np.array([m.jnt_range[m.joint(f"{b}_{s}").id] for b in LEG_BASES]) for s in "lr"}
        self.foot_body = {s: int(m.jnt_bodyid[m.joint(f"ankle_pitch_{s}").id]) for s in "lr"}
        self.ank_joint = {s: m.joint(f"ankle_pitch_{s}").id for s in "lr"}
        # sole axes and the controlled point, in the foot body frame, from the home pose
        d = mj.MjData(m)
        mj.mj_resetDataKeyframe(m, d, 0)
        mj.mj_forward(m, d)
        self.n_b, self.h_b, self.c_b = {}, {}, {}
        for s in "lr":
            g = m.geom("left_foot_bottom_tpu" if s == "l" else "right_foot_bottom_tpu").id
            mid = m.geom_dataid[g]
            v = m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid] + m.mesh_vertnum[mid]]
            w = v @ d.geom_xmat[g].reshape(3, 3).T + d.geom_xpos[g]
            c = w - w.mean(0)
            _, evec = np.linalg.eigh(c.T @ c)
            n = evec[:, 0] * (1.0 if evec[2, 0] >= 0 else -1.0)
            heading = np.array([1.0, 0.0, 0.0]) - n * n[0]
            heading /= np.linalg.norm(heading)
            lateral = np.cross(n, heading)
            a = d.xanchor[self.ank_joint[s]]
            ys = (w - a) @ lateral
            p0 = a + lateral * 0.5 * (ys.max() + ys.min())          # ankle height, laterally at the foot's centre
            R = d.xmat[self.foot_body[s]].reshape(3, 3)
            self.n_b[s], self.h_b[s], self.c_b[s] = R.T @ n, R.T @ heading, R.T @ (p0 - a)
        self.numeric_legs = self._numeric_legs
        self._warm = {s: d.qpos[self.lq[s]].copy() for s in "lr"}

    # ---- IK
    def _fk(self, base_pos, quat, ql, qr):
        d = self.d_ik
        d.qpos[:3], d.qpos[3:7] = base_pos, quat
        d.qpos[self.lq["l"]], d.qpos[self.lq["r"]] = ql, qr
        self.mj.mj_kinematics(self.model, d)
        out = {}
        for s in "lr":
            R = d.xmat[self.foot_body[s]].reshape(3, 3)
            a = d.xanchor[self.ank_joint[s]]
            out[s] = (a + R @ self.c_b[s], R @ self.n_b[s], R @ self.h_b[s])
        return out

    def _resid(self, fk, tgt, psi):
        r = {}
        cx, sx = math.cos(psi["l"]), math.sin(psi["l"])
        for s in "lr":
            p, n, h = fk[s]
            cx, sx = math.cos(psi[s]), math.sin(psi[s])
            r[s] = np.array([*(p - tgt[s]), n[0] * cx + n[1] * sx, h[0] * sx - h[1] * cx])
        return r

    def _numeric_legs(self, pelvis, yaw, pitch, ank_l, ank_r, fy_l, fy_r):
        """Levenberg-Marquardt per sample (both legs at once), warm-started from the previous sample; a sample that fails to converge is retried
        from the stand pose. Residual: ankle-height point (3), sole pitch (1), sole yaw (1); the sole roll is whatever the hip roll gives."""
        T = len(pelvis)
        quats = quat_from_yaw_pitch(yaw, pitch)
        out = {f"{b}_{s}": np.zeros(T) for b in LEG_BASES for s in "lr"}
        ok_all = np.ones(T, bool)
        ql, qr = self._warm["l"].copy(), self._warm["r"].copy()
        self.last_resid = []
        eps = 1e-6
        W = np.array([1.0, 1.0, 1.0, 0.3, 0.3])

        def solve(k, ql, qr, iters):
            tgt = {"l": ank_l[k], "r": ank_r[k]}
            psi = {"l": float(fy_l[k]), "r": float(fy_r[k])}
            lam = {"l": 1e-4, "r": 1e-4}
            fk = self._fk(pelvis[k], quats[k], ql, qr)
            r = self._resid(fk, tgt, psi)
            for it in range(iters):
                if max(np.abs(r["l"] * W).max(), np.abs(r["r"] * W).max()) < 2e-5:
                    break
                Jl, Jr = np.zeros((5, 5)), np.zeros((5, 5))
                for i in range(5):
                    dl, dr = ql.copy(), qr.copy()
                    dl[i] += eps
                    dr[i] += eps
                    r2 = self._resid(self._fk(pelvis[k], quats[k], dl, dr), tgt, psi)
                    Jl[:, i], Jr[:, i] = (r2["l"] - r["l"]) / eps, (r2["r"] - r["r"]) / eps
                new = {}
                for s, J, q in (("l", Jl, ql), ("r", Jr, qr)):
                    Jw = J * W[:, None]
                    dq = np.linalg.solve(Jw.T @ Jw + lam[s] * np.eye(5), -Jw.T @ (r[s] * W))
                    new[s] = np.clip(q + np.clip(dq, -0.2, 0.2), self.lrange[s][:, 0], self.lrange[s][:, 1])
                fk2 = self._fk(pelvis[k], quats[k], new["l"], new["r"])
                r2 = self._resid(fk2, tgt, psi)
                for s, q in (("l", ql), ("r", qr)):
                    if np.abs(r2[s] * W).max() < np.abs(r[s] * W).max():
                        q[:] = new[s]
                        r[s] = r2[s]
                        lam[s] = max(lam[s] * 0.5, 1e-8)
                    else:
                        lam[s] = min(lam[s] * 4.0, 1e3)
            return r

        home = {s: self.model.key_qpos[0][self.lq[s]].copy() if self.model.nkey else self._warm[s].copy() for s in "lr"}
        for k in range(T):
            r = solve(k, ql, qr, 30)
            bad = lambda r: max(np.abs(r["l"][:3]).max(), np.abs(r["r"][:3]).max()) > 1e-3 or max(abs(r["l"][3]), abs(r["r"][3])) > 0.02   # noqa: E731
            if bad(r):
                ql2, qr2 = home["l"].copy(), home["r"].copy()
                r2 = solve(k, ql2, qr2, 60)
                if not bad(r2) or max(np.abs(r2["l"][:3]).max(), np.abs(r2["r"][:3]).max()) < max(np.abs(r["l"][:3]).max(), np.abs(r["r"][:3]).max()):
                    ql, qr, r = ql2, qr2, r2
            self.last_resid.append((k, r["l"].copy(), r["r"].copy()))
            ok_all[k] = not bad(r)
            for i, b in enumerate(LEG_BASES):
                out[f"{b}_l"][k], out[f"{b}_r"][k] = ql[i], qr[i]
        self._warm = {"l": ql.copy(), "r": qr.copy()}
        return out, ok_all
