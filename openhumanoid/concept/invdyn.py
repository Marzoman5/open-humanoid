"""`mj_inverse` cross-check of the ideal-PD demand, and the closed-chain "fighting" diagnostics (challenge-2 row 10).

The ideal-PD harness plays a motion with a stiff torque-source PD (kp 300 N.m/rad, 12x the servo's own 24 N.m/rad) on a free base held by
a very soft tether. Two things can make its torques wrong:

1. BOOKKEEPING: units, armature, the tether wrench, the torque it logs against what the physics actually applied. Check: replay the
   logged pre-step state and the acceleration MuJoCo integrated through `mj_inverse`; the generalised force it returns must equal the
   actuator force the PD applied (plus the tether). `inverse_error` reports the RMS of the difference per joint as a share of the PD RMS.
2. CLOSED-CHAIN FIGHTING: with both feet on the floor the legs are a closed chain. A millimetre of inconsistency between the two legs'
   references makes two stiff PDs push against each other through the floor: the load shares become arbitrary and the joint torques carry
   an internal squeeze that no real servo-floor system needs. Check: in double support, the horizontal forces on the two feet should be
   the walking's own (same sign); the part that cancels between them is internal. `squeeze_bw` reports it as a share of body weight, and
   `vertical_share` the left-right load asymmetry (a symmetric stand must split 50/50).

Why not use `mj_inverse` as the demand itself: with soft contacts it produces the contact force from the CONSTRAINT VIOLATION (penetration
and its rate) of the given motion, so a reference that stands exactly on the floor gets zero contact force and the whole body weight shows
up as a base residual. The PD simulation finds the equilibrium penetration by itself, which is why it stays the demand.
"""
from __future__ import annotations

import numpy as np

from .playback import PlayConfig, play

G = 9.81


def inverse_error(robot, ref, cfg: PlayConfig | None = None) -> dict:
    import mujoco
    cfg = PlayConfig(**{**(cfg.__dict__ if cfg else {}), "mode": "ideal", "record_inverse": True})
    lg = play(robot, ref, cfg)
    model = robot.build_model(ref.scene["xml"] if ref.scene else "")
    data = mujoco.MjData(model)
    names = robot.names
    dadr = np.array([model.joint(n).dofadr[0] for n in names])
    recs = lg.extras["inverse_records"]
    warm = lg.warmup_n
    mass = lg.extras["mass_kg"]
    err = []
    act = []
    fl, fr = [], []
    for qpos, qvel, xfrc, qfa, qacc, ff in recs[warm:]:
        data.qpos[:], data.qvel[:], data.qacc[:] = qpos, qvel, qacc
        data.xfrc_applied[:] = xfrc
        mujoco.mj_inverse(model, data)
        err.append(data.qfrc_inverse[dadr] - qfa[dadr])
        act.append(qfa[dadr])
        fl.append(ff["l"]); fr.append(ff["r"])
    err, act, fl, fr = np.array(err), np.array(act), np.array(fl), np.array(fr)
    w = mass * G
    rms_act = np.sqrt((act ** 2).mean(0))
    rms_err = np.sqrt((err ** 2).mean(0))
    per = {n: {"rms_pd_nm": round(float(rms_act[j]), 4), "rms_inverse_error_nm": round(float(rms_err[j]), 5),
               "error_over_pd": round(float(rms_err[j] / max(rms_act[j], 1e-3)), 4)} for j, n in enumerate(names)}
    ds = (fl[:, 2] > 0.05 * w) & (fr[:, 2] > 0.05 * w)
    squeeze = np.zeros(len(fl))
    for ax in (0, 1):
        opp = (np.sign(fl[:, ax]) != np.sign(fr[:, ax]))
        squeeze += np.where(opp, np.minimum(np.abs(fl[:, ax]), np.abs(fr[:, ax])), 0.0) ** 2
    squeeze = np.sqrt(squeeze) / w
    out = {"samples": int(len(err)), "inverse_error_max_over_pd_leg": max(v["error_over_pd"] for n, v in per.items() if n.split("_")[0] in ("hip", "knee", "ankle")),
           "per_joint": per, "double_support_fraction": round(float(ds.mean()), 3),
           "squeeze_bw_mean_in_ds": round(float(squeeze[ds].mean()), 4) if ds.any() else None,
           "squeeze_bw_max_in_ds": round(float(squeeze[ds].max()), 4) if ds.any() else None,
           "vertical_share_left_mean_in_ds": round(float((fl[ds, 2] / np.maximum(fl[ds, 2] + fr[ds, 2], 1e-6)).mean()), 3) if ds.any() else None,
           "tether_mean_bw": round(float(lg.extras["assist_mean_bw"]), 4)}
    return out
