"""Static wrench recursion on the link tree.

For a scenario (pose q, external point forces, an effective gravity/inertia field g_eff in m/s2) it returns, for every joint j, the load wrench the
DISTAL subtree puts on the joint:   W_j = (F, M about the joint axis origin O_j)   in the world frame, N and N.mm.
`M . a_j` is the joint torque the servo has to supply (or react).

Units: forces N, lengths mm, moments N.mm, masses kg, field m/s2 (force on a mass m is m * g_eff in N).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .model import Model

G = 9.80665


@dataclass
class Contact:
    link: str
    point: np.ndarray            # world (mm)
    force: np.ndarray            # world (N), load ON the robot
    label: str = ""


@dataclass
class Scenario:
    name: str
    cls: str                      # safety-factor class (policy `safety_factors`)
    desc: str
    q: dict[str, float] = field(default_factory=dict)
    g_eff: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, -G]))
    contacts: list[Contact] = field(default_factory=list)
    kind: str = "assumption"      # provenance of the magnitude: sourced | derived | assumption
    prov: str = ""
    root: str | None = None       # link whose subtree is analysed (None = every link)
    cap_factor: float | None = None   # scale the external loading so no joint torque exceeds cap_factor x stall (None: not servo limited)
    cap_mode: str = "contacts"        # contacts | field
    cap_nm: dict | None = None        # per-joint absolute torque caps (N.m); overrides cap_factor x stall for the joints listed
    info: dict = field(default_factory=dict)


def link_masses(model: Model, link: str, mass_override: dict[str, float] | None = None) -> list[tuple[str, float, np.ndarray]]:
    """[(part id, kg, com in the link frame)] of every part in the link (printed and purchased)."""
    out = []
    for p in model.parts_in(link):
        m = (mass_override or {}).get(p.id, p.mass_kg)
        if m > 0:
            out.append((p.id, m, p.com))
    return out


def joint_wrenches(model: Model, sc: Scenario, mass_override: dict[str, float] | None = None,
                   only_joints: list[str] | None = None) -> dict[str, dict]:
    """Per joint: {'F': (3,), 'M': (3,) about O_j, 'O': (3,), 'axis': (3,), 'tau': M.axis} (world)."""
    fk = model.fk(sc.q)
    # loads per link: (F, M about the world origin)
    F_l: dict[str, np.ndarray] = {n: np.zeros(3) for n in model.links}
    M_l: dict[str, np.ndarray] = {n: np.zeros(3) for n in model.links}
    for n in model.links:
        R, t = fk[n]
        for _pid, m, com in link_masses(model, n, mass_override):
            pw = R @ com + t
            f = m * sc.g_eff
            F_l[n] += f
            M_l[n] += np.cross(pw, f)
    for c in sc.contacts:
        F_l[c.link] += c.force
        M_l[c.link] += np.cross(c.point, c.force)
    out: dict[str, dict] = {}
    for jn, j in model.joints.items():
        if only_joints and jn not in only_joints:
            continue
        sub = model.subtree(j.child_link)
        F = sum((F_l[n] for n in sub), np.zeros(3))
        Mo = sum((M_l[n] for n in sub), np.zeros(3))
        O, a = model.world_axis(jn, fk)
        M = Mo - np.cross(O, F)
        out[jn] = {"F": F, "M": M, "O": O, "axis": a, "tau": float(M @ a)}
    return out


def scale_to_cap(model: Model, sc: Scenario, stall: dict[str, float], mass_override: dict[str, float] | None = None) -> float:
    """Scale factor s in [0, 1] on the external loading (contact forces, or the whole inertial field for cap_mode 'field') such that
    |tau_j| <= cap_factor * stall_j for every joint. Torque is linear in s: tau(s) = tau0 + s (tau1 - tau0)."""
    if sc.cap_factor is None:
        return 1.0
    if sc.cap_mode == "field":
        base = Scenario(sc.name, sc.cls, "", sc.q, np.zeros(3), [])
    else:
        base = Scenario(sc.name, sc.cls, "", sc.q, sc.g_eff, [])
    w0 = joint_wrenches(model, base, mass_override)
    w1 = joint_wrenches(model, sc, mass_override)
    s = 1.0
    for jn, d in w1.items():
        cap = (sc.cap_nm[jn] if sc.cap_nm and jn in sc.cap_nm else stall.get(jn, 0.0) * sc.cap_factor) * 1000.0
        if cap <= 0:
            continue
        t0, t1 = w0[jn]["tau"], d["tau"]
        if abs(t1) <= cap:
            continue
        dt = t1 - t0
        if abs(dt) < 1e-9:
            continue
        sols = [(sg * cap - t0) / dt for sg in (1.0, -1.0)]
        sols = [x for x in sols if 0.0 <= x < s]
        if sols:
            s = min(sols)
    # single-sided joints (no idler bearing): the non-axial moment goes through the servo's output shaft; it cannot exceed what the servo
    # transmits either (policy joint_torque.side_moment_over_stall x stall; ASSUMPTION, bench test in docs/strength.md)
    from .policy import policy, pv

    fperp = float(pv(policy(), "joint_torque", "side_force_n", default=0.0))
    if fperp > 0 and sc.cap_factor is not None:
        for jn, d in w1.items():
            if model.joints[jn].idler_bearing:
                continue
            a = d["axis"]
            f1 = d["F"] - a * float(d["F"] @ a)
            f0 = w0[jn]["F"] - a * float(w0[jn]["F"] @ a)
            if np.linalg.norm(f1) <= fperp:
                continue
            dm = f1 - f0
            A_, B_, C_ = float(dm @ dm), 2.0 * float(f0 @ dm), float(f0 @ f0) - fperp * fperp
            if A_ < 1e-12:
                continue
            disc = B_ * B_ - 4 * A_ * C_
            if disc < 0:
                continue
            root = (-B_ + math.sqrt(disc)) / (2 * A_)
            if 0.0 <= root < s:
                s = root
    kperp = float(pv(policy(), "joint_torque", "side_moment_over_stall", default=0.0))
    if kperp > 0 and sc.cap_factor is not None:
        for jn, d in w1.items():
            if model.joints[jn].idler_bearing:
                continue
            cap = kperp * stall.get(jn, 0.0) * 1000.0
            a = d["axis"]
            m1 = d["M"] - a * float(d["M"] @ a)
            m0 = w0[jn]["M"] - a * float(w0[jn]["M"] @ a)
            if cap <= 0 or np.linalg.norm(m1) <= cap:
                continue
            dm = m1 - m0
            A_, B_, C_ = float(dm @ dm), 2.0 * float(m0 @ dm), float(m0 @ m0) - cap * cap
            if A_ < 1e-12:
                continue
            disc = B_ * B_ - 4 * A_ * C_
            if disc < 0:
                continue
            root = (-B_ + math.sqrt(disc)) / (2 * A_)
            if 0.0 <= root < s:
                s = root
    return max(0.0, min(1.0, s))


def apply_scale(sc: Scenario, s: float) -> None:
    if s >= 0.9999:
        return
    if sc.cap_mode == "field":
        sc.g_eff = sc.g_eff * s
    else:
        for c in sc.contacts:
            c.force = c.force * s
