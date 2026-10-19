"""Joint-torque demand by inverse dynamics with a MINIMUM-TORQUE contact-force distribution.

The ideal-PD harness (`envelopes.ideal_demand`) is what every candidate is judged with. It needs the motion to be playable open loop: a
tether, a stable base, and legs that do not fight through the floor. A reference that is not (an RL imitation target such as Open Duck Mini's
own reference motion, or a gait on a mechanism it was not made for) cannot be measured that way. This module gives the demand of ANY
joint-space reference without simulating it:

  1. q, dq, ddq of the whole system (free base included) from the reference by finite differences (`mj_differentiatePos`);
  2. `mj_inverse` with contacts DISABLED returns the generalised force that produces that motion: g;
  3. the stance feet supply it through sole-corner forces f (unilateral: normal >= 0), chosen to MINIMISE the sum of squared joint torques
     tau_j = g_j - A_j f subject to the six base equations A_base f = g_base (a weighted least-squares problem with bounds);
  4. the base-equation mismatch, as a share of body weight, says how dynamically inconsistent the reference is (0 for a balanced motion);
     the share of samples where the resulting foot force leaves the friction cone (mu 0.8) is reported as well.

Because the contact split is the best the geometry allows, the torques are a LOWER BOUND for any controller on that motion, and they carry
no closed-chain fighting. BAM friction is added like for every demand.
"""
from __future__ import annotations

import numpy as np

from ..actuators import ServoBank, friction_budget
from .envelopes import Demand
from .kin import Reference, catmull

G = 9.81


def sole_points(model, data, side: str) -> tuple:
    """(body id, 4 sole corners in the body frame) of foot `side`: the x-y bounding rectangle of the lowest surface of the foot's collision
    geometry at the pose in `data` (a standing pose: flat foot). Box feet and mesh soles both work."""
    import mujoco
    mujoco.mj_forward(model, data)
    cand = [g for g in range(model.ngeom) if model.geom_contype[g] and "foot" in model.geom(g).name
            and (model.geom(g).name.endswith(f"_{side}") or model.geom(g).name.startswith("left" if side == "l" else "right"))]
    g = cand[0]
    body = int(model.geom_bodyid[g])
    if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
        mid = model.geom_dataid[g]
        v = model.mesh_vert[model.mesh_vertadr[mid]:model.mesh_vertadr[mid] + model.mesh_vertnum[mid]]
        w = v @ data.geom_xmat[g].reshape(3, 3).T + data.geom_xpos[g]
    else:
        sx, sy, sz = model.geom_size[g][:3]
        loc = np.array([[a * sx, b * sy, c * sz] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])
        w = loc @ data.geom_xmat[g].reshape(3, 3).T + data.geom_xpos[g]
    zmin = w[:, 2].min()
    low = w[w[:, 2] < zmin + 0.006]
    x0, x1, y0, y1 = low[:, 0].min(), low[:, 0].max(), low[:, 1].min(), low[:, 1].max()
    pts = np.array([[x0, y0, zmin], [x1, y0, zmin], [x1, y1, zmin], [x0, y1, zmin]])
    R = data.xmat[body].reshape(3, 3)
    return body, (pts - data.xpos[body]) @ R


def min_torque_demand(robot, ref: Reference, *, sim_dt: float = 0.005, stance=None, mu: float = 0.8, stand_pose=None) -> Demand:
    """See the module docstring. `stance` (T,2) bool: feet carrying load (default ref.stance, else both). `stand_pose`: joint vector in which
    the soles are flat, to find the sole corners (default: all joints zero + the robot's stand)."""
    import mujoco
    from scipy.optimize import lsq_linear
    model = robot.build_model(ref.scene["xml"] if ref.scene else "")
    model.opt.disableflags |= mujoco.mjtDisableBit.mjDSBL_CONTACT
    data = mujoco.MjData(model)
    names = robot.names
    qadr = np.array([model.joint(n).qposadr[0] for n in names])
    dadr = np.array([model.joint(n).dofadr[0] for n in names])
    d0 = mujoco.MjData(model)
    d0.qpos[:7] = [0, 0, 0.3, 1, 0, 0, 0]
    d0.qpos[qadr] = ref.q[0] if stand_pose is None else stand_pose
    foot = {s: sole_points(model, d0, s) for s in "lr"}
    n_main = int(round(ref.duration / sim_dt)) + 1
    t = np.arange(n_main) * sim_dt
    tc = np.clip(t, 0, ref.duration)
    Q = catmull(ref.t, ref.q, tc)
    P = catmull(ref.t, ref.base_pos, tc)
    U = catmull(ref.t, ref.base_quat, tc)
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    qpos = np.zeros((n_main, model.nq))
    for k in range(n_main):
        qpos[k, :3], qpos[k, 3:7], qpos[k, qadr] = P[k], U[k], Q[k]
    qvel = np.zeros((n_main, model.nv))
    for k in range(1, n_main - 1):
        mujoco.mj_differentiatePos(model, qvel[k], 2 * sim_dt, qpos[k - 1], qpos[k + 1])
    qvel[0], qvel[-1] = qvel[1], qvel[-2]
    qacc = np.gradient(qvel, sim_dt, axis=0)
    ker = np.ones(3) / 3
    qacc = np.stack([np.convolve(np.pad(qacc[:, j], 1, mode="edge"), ker, mode="valid") for j in range(model.nv)], 1)
    st = ref.stance if stance is None else stance
    if st is None:
        st = np.ones((len(ref.q), 2), bool)
    st_i = np.stack([np.interp(t, ref.t, np.asarray(st)[:, i].astype(float)) for i in range(2)], 1) > 0.5
    mass = float(model.body_mass.sum())
    w_eq = 1e3
    tau = np.zeros((n_main, len(names)))
    resid = np.zeros(n_main)
    outside = np.zeros(n_main, bool)
    jacp = np.zeros((3, model.nv))
    for k in range(n_main):
        data.qpos[:], data.qvel[:], data.qacc[:] = qpos[k], qvel[k], qacc[k]
        mujoco.mj_inverse(model, data)
        g = data.qfrc_inverse.copy()
        loaded = [s for i, s in enumerate("lr") if st_i[k, i]]
        if not loaded:
            tau[k] = g[dadr]
            resid[k] = np.linalg.norm(g[:3]) / (mass * G)
            outside[k] = True
            continue
        cols = []
        for s in loaded:
            body, loc = foot[s]
            R = data.xmat[body].reshape(3, 3)
            for p in loc:
                mujoco.mj_jac(model, data, jacp, None, data.xpos[body] + R @ p, body)
                cols.append(jacp.T.copy())
        A = np.concatenate(cols, axis=1)
        nvar = A.shape[1]
        rows = np.concatenate([w_eq * A[:6], -A[dadr]], axis=0)
        rhs = np.concatenate([w_eq * g[:6], -g[dadr]])
        lo = np.full(nvar, -np.inf)
        hi = np.full(nvar, np.inf)
        lo[2::3] = 0.0
        f = lsq_linear(rows, rhs, bounds=(lo, hi), method="bvls", max_iter=300).x
        tau[k] = g[dadr] - A[dadr] @ f
        resid[k] = np.linalg.norm(A[:3] @ f - g[:3]) / (mass * G)
        fz = f[2::3].sum()
        outside[k] = np.hypot(f[0::3].sum(), f[1::3].sum()) > mu * max(fz, 1e-6)
    ratio = robot.ratio
    eff = robot.eff if robot.eff is not None else np.ones(len(names))
    om = qvel[:, dadr] / ratio
    tau_s = tau * ratio * np.where(tau * om >= 0, 1.0 / eff, eff)
    bank = ServoBank([robot.servo[n] for n in names], 0.01)
    fl, d = friction_budget(bank.fr, tau_s, -tau_s, om)
    tau_dem = tau_s + np.sign(om) * (fl + d * np.abs(om)) * (np.abs(om) > 0.05)
    i0 = int(0.2 / sim_dt)
    win = slice(i0, len(t) - 1)
    if "walk_window" in ref.meta:
        a, b = ref.meta["walk_window"]
        win = slice(max(int(np.searchsorted(t, a)), i0), max(int(np.searchsorted(t, b)), i0 + 2))
    dem = Demand(ref.name + "_mintorque", t, tau_dem, tau_s, om, names, win, True, "", float(resid[win].mean()), float(resid[win].max()), False, list(ref.notes))
    dem.log = None
    dem.base_residual_bw = resid
    dem.friction_cone_violations = float(outside[win].mean())
    return dem
