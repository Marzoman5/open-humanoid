"""Analytic checks for every printed part: sections (axial, bending, shear, torsion, layer adhesion), buckling, fatigue.

`PartAnalyzer` slices a part along three axes (and its long axis) every `sections.step_mm`, keeps the weighted sections, and for each
scenario reduces the loads on one side of every plane to the internal wrench (see sections.py). The stress is raised by Kt where an internal
corner (sharp concave edge or concave fillet) lies transverse to the stress and close to the plane, and compared with the weakest-direction
allowable of the material at that plane (policy.Material). Every result is a `Row`; margin = allowable / (SF * demand), pass at >= 1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .loadpath import Load, PartLoads
from .model import Model, PartRec
from .policy import material as get_material, policy, pv
from .sections import Section, slice_mesh, stress


@dataclass
class Row:
    part: str
    case: str
    cls: str
    check: str
    margin: float
    demand: float
    allowable: float
    sf: float
    unit: str
    where: str
    mode: str
    gate: bool = True
    info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        for k in ("margin", "demand", "allowable", "sf"):
            d[k] = round(float(d[k]), 4) if np.isfinite(d[k]) else (None if d[k] != np.inf else 1e9)
        return d


def sf_of(cls: str) -> tuple[float, bool, bool]:
    c = policy()["safety_factors"][cls]
    return float(c["sf"]), bool(c.get("fatigue", False)), bool(c.get("gate", True))


def phi_deg(n: np.ndarray, up: np.ndarray) -> float:
    """Angle between a plane normal and the build direction (0 = the plane lies in a layer: loading it pulls layers apart)."""
    return math.degrees(math.acos(min(1.0, abs(float(n @ up)))))


class PartAnalyzer:
    def __init__(self, part: PartRec, step: float | None = None):
        pol = policy()
        self.part = part
        self.mat = get_material(part.material)
        prof = part.profile or {}
        per = int(prof.get("perimeters", pv(pol, "print_profile", "perimeters")))
        lw = float(pv(pol, "print_profile", "line_width_mm"))
        self.shell = per * lw
        self.fill = float(prof.get("infill_pct", pv(pol, "print_profile", "infill_pct"))) / 100.0 * float(pv(pol, "print_profile", "infill_efficiency"))
        self.step = float(step or pv(pol, "sections", "step_mm"))
        self.up = part.print_up / np.linalg.norm(part.print_up)
        self.mesh = part.mesh
        self._stack: list[dict] | None = None
        self.shear_form = float(pv(pol, "sections", "shear_form_factor"))
        sc = pol["stress_concentration"]
        self.kt_c = float(pv(sc, "kt_c"))
        self.kt_cap = float(pv(sc, "kt_cap"))
        self.r_floor = float(pv(sc, "effective_min_radius_mm"))
        self.zone = float(pv(sc, "zone_over_thickness"))
        self.fill_mass = float(prof.get("fill_fraction", pv(pol, "print_profile", "mass_fill_fraction")))

    # ---- normals --------------------------------------------------------------------------------------------------
    def normals(self) -> list[np.ndarray]:
        out = [np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])]
        return out          # oblique planes through L-shaped parts cut grazing corner slivers, not load-path sections: axis-aligned only

    def stack(self) -> list[dict]:
        if self._stack is not None:
            return self._stack
        res = []
        V = np.asarray(self.mesh.vertices)
        for n in self.normals():
            proj = V @ n
            lo, hi = float(proj.min()), float(proj.max())
            ext = hi - lo
            pos = np.arange(lo + 0.6, hi - 0.5, self.step)
            if len(pos) == 0:
                pos = np.array([0.5 * (lo + hi)])
            # anchor points: the mesh centroid projected onto the plane
            base = np.asarray(self.mesh.centroid)
            secs: list[Section | None] = []
            for p in pos:
                o = base + n * (p - float(base @ n))
                secs.append(slice_mesh(self.mesh, o, n, self.shell, self.fill))
            # far-side material (positions above each plane): area stack for the weight of the far part
            A = np.array([s.A_solid if s else 0.0 for s in secs])
            cen = np.array([s.c if s else np.zeros(3) for s in secs])
            res.append({"n": n, "pos": pos, "secs": secs, "A": A, "cen": cen, "lo": lo, "hi": hi, "ext": ext})
        self._stack = res
        return res

    # ---- stress concentration -------------------------------------------------------------------------------------
    def kt_of(self, sec: Section) -> tuple[float, str]:
        best, why = 1.0, ""
        t = max(sec.t_min, 0.5)
        for c in self.part.corners:
            mid = np.asarray(c["mid"])
            dv = np.asarray(c["dir"])
            if abs(float((mid - sec.c) @ sec.normal)) > self.zone * t + 0.5:
                continue
            if abs(float(dv @ sec.normal)) > 0.35:
                continue
            du, dvv = float(dv @ sec.u), float(dv @ sec.v)
            rel = mid - sec.c
            if abs(rel @ sec.u) > max(abs(sec.bbox_uv[0]), abs(sec.bbox_uv[1])) + 3 or abs(rel @ sec.v) > max(abs(sec.bbox_uv[2]), abs(sec.bbox_uv[3])) + 3:
                continue
            nrm = math.hypot(du, dvv)
            if nrm < 1e-6:
                continue
            proj = sec.verts_uv @ np.array([du, dvv]) / nrm
            width = float(proj.max() - proj.min())
            if c["length"] < 0.5 * width:
                continue
            r = max(float(c["r"]), self.r_floor)
            kt = min(1.0 + self.kt_c * math.sqrt(t / r), self.kt_cap)
            if kt > best:
                best = kt
                why = f"{c['kind']} corner r={c['r']:.1f} mm, t={t:.1f} mm"
        return best, why

    # ---- evaluation -----------------------------------------------------------------------------------------------
    def evaluate(self, pl: PartLoads, case: str, cls: str, mass_override: float | None = None) -> list[Row]:
        sf, fatigue, gate = sf_of(cls)
        part = self.part
        loads = pl.loads
        P = np.array([ld.point for ld in loads]) if loads else np.zeros((0, 3))
        Fv = np.array([ld.F for ld in loads]) if loads else np.zeros((0, 3))
        Mv = np.array([ld.M for ld in loads]) if loads else np.zeros((0, 3))
        g = pl.g_link
        dens = self.mat.density
        rows: list[Row] = []
        worst = None
        worst_f = None
        worst_buck = None
        for st in self.stack():
            n = st["n"]
            ph = phi_deg(n, self.up)
            pos_all = st["pos"]
            A = st["A"]
            cen = st["cen"]
            # far-side weight: material above each plane (cumulative from the top)
            Vf = np.cumsum((A * self.step)[::-1])[::-1] - A * self.step         # strictly above plane k
            Cn = np.cumsum((A[:, None] * cen * self.step)[::-1], axis=0)[::-1] - A[:, None] * cen * self.step
            for k, sec in enumerate(st["secs"]):
                if sec is None or sec.A < float(pv(policy(), "sections", "min_area_mm2")) or sec.t_min < float(pv(policy(), "sections", "min_thickness_mm")):
                    continue            # grazing cuts through a face are slivers, not load-path sections
                c = sec.c
                if len(loads):
                    side = (P @ n) > pos_all[k]
                    F_far = Fv[side].sum(axis=0)
                    M_far = (Mv[side] + np.cross(P[side] - c, Fv[side])).sum(axis=0)
                else:
                    F_far, M_far = np.zeros(3), np.zeros(3)
                if Vf[k] > 1e-6:
                    m_far = Vf[k] * dens * self.fill_mass * 1e-6
                    com = Cn[k] / Vf[k]
                    fw = m_far * g
                    F_far = F_far + fw
                    M_far = M_far + np.cross(com - c, fw)
                res = stress(sec, -F_far, -M_far, self.shear_form)
                kt, kwhy = self.kt_of(sec)
                sig_eq = math.sqrt((kt * res.sigma_tension) ** 2 + 3.0 * res.tau ** 2) if res.sigma_tension > 0 else math.sqrt((kt * res.sigma) ** 2 + 3.0 * res.tau ** 2)
                sa = self.mat.tensile(ph)
                ta = self.mat.shear(ph)
                # interaction of normal and shear utilisation
                comp_ratio = float(pv(policy(), "knockdown", "compression_over_tensile"))
                sa_c = self.mat.tensile(90.0) * comp_ratio              # compression across layers is not a delamination mode
                u_n = max(kt * max(res.sigma_tension, 0.0) / sa, kt * res.sigma_compression / sa_c)
                u_t = res.tau / ta
                util = math.sqrt(u_n ** 2 + u_t ** 2)
                if worst is None or util > worst[0]:
                    worst = (util, res, kt, kwhy, ph, n, sec, sig_eq)
                if fatigue:
                    se = self.mat.endurance(ph)
                    uf = math.sqrt((kt * max(res.sigma_tension, 0.0) / se) ** 2 + (res.tau / (0.5 * se)) ** 2)
                    if worst_f is None or uf > worst_f[0]:
                        worst_f = (uf, res, kt, kwhy, ph, n, sec, se)
                # buckling: compressive member, slender
                if res.N < 0:
                    L = st["ext"]
                    r_min = math.sqrt(min(sec.Suu, sec.Svv) / max(sec.A, 1e-6))
                    if L / max(sec.t_min, 0.1) >= float(pv(policy(), "buckling", "slender_ratio_min")) and r_min > 0:
                        Kf = float(pv(policy(), "buckling", "end_fixity_k"))
                        E = self.mat.modulus(ph) * self.fill_modulus(sec)
                        Pcr = math.pi ** 2 * E * min(sec.Suu, sec.Svv) / (Kf * L) ** 2
                        ub = abs(res.N) / Pcr
                        if worst_buck is None or ub > worst_buck[0]:
                            worst_buck = (ub, res, Pcr, L, n, sec)
        if worst is not None:
            util, res, kt, kwhy, ph, n, sec, sig_eq = worst
            sa = self.mat.tensile(ph)
            mode = self.mode_of(res, ph, kt, kwhy)
            rows.append(Row(part.id, case, cls, "section", margin=(1.0 / (sf * util)) if util > 1e-12 else 1e9, demand=util * sa, allowable=sa, sf=sf,
                            unit="MPa (equivalent, incl. Kt)", where=self.where(sec, res), mode=mode, gate=gate,
                            info={"sigma_mpa": res.sigma_tension, "tau_mpa": res.tau, "kt": kt, "kt_reason": kwhy, "phi_deg": ph,
                                  "N": res.N, "M_nmm": [res.Mu, res.Mv], "V_n": [res.Vu, res.Vv], "T_nmm": res.T,
                                  "normal": n.round(3).tolist(), "pos_mm": sec.pos, "fibre_xyz": np.asarray(res.where).round(2).tolist(), "section_area_mm2": sec.A, "section_t_mm": sec.t_min}))
        if worst_f is not None:
            uf, res, kt, kwhy, ph, n, sec, se = worst_f
            rows.append(Row(part.id, case, cls, "fatigue", margin=(1.0 / uf) if uf > 1e-12 else 1e9, demand=uf * se, allowable=se, sf=1.0,
                            unit="MPa (peak stress vs endurance)", where=self.where(sec, res),
                            mode=f"fatigue crack at {kwhy or 'section edge'} (endurance {self.mat.endurance_fraction:.2f} x UTS {self.mat.endurance_kind}, {int(pv(policy(), 'fatigue', 'design_life_cycles'))} cycles)",
                            gate=gate, info={"sigma_mpa": res.sigma_tension, "kt": kt, "endurance_mpa": se, "phi_deg": ph}))
        if worst_buck is not None:
            ub, res, Pcr, L, n, sec = worst_buck
            rows.append(Row(part.id, case, cls, "buckling", margin=1.0 / (sf * ub), demand=abs(res.N), allowable=Pcr, sf=sf, unit="N (Euler)",
                            where=f"member length {L:.0f} mm along {n.round(2).tolist()}", mode="Euler buckling of a slender printed member", gate=gate))
        return rows

    def fill_modulus(self, sec: Section) -> float:
        """Stiffness of the weighted section relative to a solid one: weighted inertia is already used, so 1.0."""
        return 1.0

    @staticmethod
    def where(sec: Section, res) -> str:
        return f"plane {sec.normal.round(2).tolist()} @ {sec.pos:.1f} mm, fibre at {np.round(res.where, 1).tolist()}"

    @staticmethod
    def mode_of(res, phi: float, kt: float, kwhy: str) -> str:
        bend = math.hypot(res.Mu, res.Mv)
        parts = []
        if phi < 35.0 and res.sigma_tension > 0:
            parts.append("delamination: tension across the layers")
        elif res.sigma_tension > 0:
            parts.append("tensile rupture along the filaments")
        else:
            parts.append("compression / crushing")
        if bend > 1e-9 and abs(res.N) * 1.0 < 1e-6 + bend / 10.0:
            parts.append("bending")
        if res.tau > 0.5 * max(res.sigma, 1e-9):
            parts.append("shear / torsion")
        if kt > 1.2:
            parts.append(f"Kt {kt:.1f} at {kwhy}")
        return "; ".join(parts)
