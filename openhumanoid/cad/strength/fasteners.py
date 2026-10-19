"""Feature checks: horn bolt circle, bolted connections between printed parts, idler bearing seats, assembly clamp.

Capacities come from the policy (strength.yaml) and the material model; the demands from the load path. Same Row/margin convention as analytic.py.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point

from .analytic import Row, phi_deg, sf_of
from .joints import (HEAD_D, HOLE_D, SHANK_D, THREAD_AREA, Connection, build_connection, solve_connection)
from .loadpath import PartLoads, Topology, edge_of
from .model import JointRec, Model, PartRec
from .policy import material as get_material, policy, pv
from .sections import plane_basis, section_geometry

LOW_CB_DEPTH = {"M2": 1.8, "M2.5": 2.05, "M3": 2.3}          # components/data/hardware.yaml: DIN 7984 k + 0.3
INSERT_LEN = {"M2": 3.0, "M2.5": 4.0, "M3": 5.7}
BEARING_OD = {"MR105ZZ": 10.0, "MR85ZZ": 8.0, "MR83ZZ": 8.0, "623ZZ": 10.0, "685ZZ": 11.0, "625ZZ": 16.0, "MR126ZZ": 12.0, "606ZZ": 17.0, "688ZZ": 16.0}
BEARING_W = {"MR105ZZ": 4.0, "MR85ZZ": 2.5, "MR83ZZ": 3.0, "623ZZ": 4.0, "685ZZ": 5.0, "625ZZ": 5.0, "MR126ZZ": 4.0, "606ZZ": 6.0, "688ZZ": 5.0}
SCREW_YIELD = 450.0          # MPa, A2-70 stainless (the weaker of the likely bought screws)


def _thickness(mesh, p: np.ndarray, d: np.ndarray, offsets: list[np.ndarray]) -> float:
    """Median thickness of the first material slab met going along `d` from `p + offset`, probing with rays parallel to d."""
    vals = []
    for off in offsets:
        o = p + off - d * 8.0
        try:
            locs, _, _ = mesh.ray.intersects_location([o], [d])
        except Exception:  # noqa: BLE001
            continue
        if len(locs) < 2:
            continue
        t = np.sort((locs - o) @ d)
        # pair entries/exits
        for i in range(0, len(t) - 1, 2):
            vals.append(float(t[i + 1] - t[i]))
            break
    return float(np.max(vals)) if vals else float("nan")      # the full slab: probes that fall in a counterbore return only the floor


def _perp(d: np.ndarray, r: float, n: int = 12, rot: float = 0.2) -> list[np.ndarray]:
    u, v, _ = plane_basis(d)
    return [r * (math.cos(rot + 2 * math.pi * i / n) * u + math.sin(rot + 2 * math.pi * i / n) * v) for i in range(n)]


def shear_allow(mat, axis: np.ndarray, up: np.ndarray) -> float:
    """Shear allowable for a plug pushed ALONG `axis` (hole axis): along the build direction the cylinder wall cuts filaments (XY value);
    across it the wall includes layer interfaces (Z value)."""
    ph = phi_deg(axis, up)
    return mat.shear(90.0 - ph)


def horn_checks(model: Model, topo: Topology, j: JointRec, pl: PartLoads, part: PartRec, case: str, cls: str, tau_cap_nmm: float | None = None) -> list[Row]:
    sf, _fat, gate = sf_of(cls)
    hr = [ld for ld in pl.loads if ld.label.startswith("horn reaction")]
    if not hr:
        return []
    mat = get_material(part.material)
    a = j.servo_z / np.linalg.norm(j.servo_z)
    Fh = sum((ld.F for ld in hr), np.zeros(3))
    Mh = sum((ld.M for ld in hr), np.zeros(3))
    tau = float(Mh @ a)
    if tau_cap_nmm is not None:
        tau = math.copysign(tau_cap_nmm, tau) if tau != 0 else tau_cap_nmm
        Mh = a * tau
        Fh = np.zeros(3)
    Mperp = Mh - a * (Mh @ a)
    Fax = float(Fh @ a)
    Fperp = Fh - a * Fax
    n = j.horn_n_holes
    r = j.horn_bolt_circle_d / 2.0
    th = j.horn_screw
    V = abs(tau) / (n * r) + float(np.linalg.norm(Fperp)) / n
    # tension of each horn screw from the non-axial moment: the bolts sit at their real positions (horn component: 45 deg off the servo x axis on the
    # bolt circle), the neutral axis is the moment direction, lever_i = (a x r_i) . m_hat, T_i = |M| lever_i / sum lever_k^2
    xs = j.servo_x / np.linalg.norm(j.servo_x)
    ys = np.cross(a, xs)
    ang0 = math.radians(float((part.meta or {}).get("horn_clock_deg", 0.0)) + 45.0)
    pos = [r * (math.cos(ang0 + 2 * math.pi * k / n) * xs + math.sin(ang0 + 2 * math.pi * k / n) * ys) for k in range(n)]
    Mn = float(np.linalg.norm(Mperp))
    if Mn > 1e-9:
        mh = Mperp / Mn
        lev = np.array([float(np.cross(a, p_) @ mh) for p_ in pos])
        T_m = float((Mn * lev / max((lev ** 2).sum(), 1e-9)).max())
    else:
        T_m = 0.0
    T = max(T_m, 0.0) + abs(Fax) / n
    from .loadpath import horn_thickness

    hs = j.horn_seat - model.fk({})[j.child_link][1] - model.if_offset + horn_thickness(model, j) * a        # plate underside (on the horn top)
    off = _perp(a, r)
    cb = LOW_CB_DEPTH.get(th, 1.8)
    t_pl = _thickness(part.mesh, hs, a, off)
    t_floor = max((t_pl - cb) if np.isfinite(t_pl) else 1.6, 0.8)
    d_s, d_h, D_h = SHANK_D.get(th, 2.0), HOLE_D.get(th, 2.4), HEAD_D.get(th, 3.8)
    wsh = (part.meta or {}).get("horn_washer_od_mm")                          # builder: horn_mount(washer_od=...) records it on the part
    if wsh:
        D_h = float(wsh)
    rows = []
    # bearing of the screw shank on the hole wall
    sig_br = V / (d_s * t_floor)
    allow_br = mat.bearing(90.0)
    rows.append(Row(part.id, case, cls, "horn_bearing", allow_br / (sf * sig_br) if sig_br > 1e-9 else 1e9, sig_br, allow_br, sf, "MPa",
                    f"{j.name}: {n} x {th} on a {2 * r:.0f} mm circle, shank {t_floor:.1f} mm in the plate", "horn screw bears on the plate under the counterbore", gate,
                    {"V_per_screw_n": V, "tau_nmm": tau, "t_plate_mm": t_pl}))
    # tear-out towards the plate edge
    sec = section_geometry(part.mesh, hs + a * 0.5 * (t_pl if np.isfinite(t_pl) else 4.0), a)
    if sec is not None:
        u, v, nn = plane_basis(a)
        geom = sec[0]
        ext = geom.exterior if geom.geom_type == "Polygon" else max(geom.geoms, key=lambda q: q.area).exterior
        best = min(Point(p[0], p[1]).distance(ext) for p in [np.array([r * math.cos(t), r * math.sin(t)]) for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)])
        ligament = max(best - d_h / 2.0, 0.1)
        cap = 2.0 * ligament * t_floor * shear_allow(mat, a, part.print_up)
        rows.append(Row(part.id, case, cls, "horn_tear_out", cap / (sf * V) if V > 1e-9 else 1e9, V, cap, sf, "N",
                        f"{j.name}: ligament {ligament:.1f} mm from the bolt hole to the plate edge", "horn screw tears out through the plate edge", gate))
    # head pull-through (axial) and screw capacity
    if T > 1e-9:
        head_area = math.pi / 4.0 * (D_h ** 2 - d_h ** 2)
        p_head = T / head_area
        allow_c = mat.tensile(90.0)
        punch = math.pi * D_h * t_floor * shear_allow(mat, a, part.print_up)
        rows.append(Row(part.id, case, cls, "horn_pull_through", min(allow_c / (sf * p_head), punch / (sf * T)), T, min(allow_c * head_area, punch), sf, "N",
                        f"{j.name}: axial pull on a horn screw", "screw head pulls through the plate floor", gate))
    cap_s = 0.6 * SCREW_YIELD * THREAD_AREA.get(th, 2.07)
    rows.append(Row(part.id, case, cls, "horn_screw", cap_s / (sf * max(V, 1e-9)), V, cap_s, sf, "N", f"{j.name}: horn screw shear", "steel screw shears", gate))
    return rows


def connection_checks(model: Model, topo: Topology, con: Connection, pl_child: PartLoads, case: str, cls: str, part_rec: dict[str, PartRec]) -> list[Row]:
    sf, _fat, gate = sf_of(cls)
    ed = pl_child.reaction_to_parent
    if ed is None or ed.wrench_F is None:
        return []
    F_edge, M_edge = ed.wrench_F, ed.wrench_M
    Mc = M_edge + np.cross(ed.centroid - con.centroid, F_edge)
    if con.insert_part == ed.parent:
        F_ins, M_ins = F_edge, Mc
    else:
        F_ins, M_ins = -F_edge, -Mc
    res = solve_connection(con, F_ins, M_ins)
    ins, scr = part_rec[con.insert_part], part_rec[con.screw_part]
    m_i, m_s = get_material(ins.material), get_material(scr.material)
    th = con.bolts[0]["thread"]
    rows = []
    pull_ref = float(pv(policy()["fasteners"], "insert_pullout_n", th, default=300.0) if False else policy()["fasteners"]["insert_pullout_n"][th]["v"])
    ref = get_material(policy()["fasteners"]["insert_ref_material"])
    scale = m_i.tensile(90.0) / ref.tensile(90.0)
    ax_phi = phi_deg(con.d, ins.print_up)
    orient = m_i.tensile(ax_phi) / m_i.tensile(90.0)
    pull_cap = pull_ref * scale * orient
    where = f"{con.child} -> {con.parent}: {len(con.bolts)} x {th}, patch {con.patch_area:.0f} mm2"
    Tmax = max(res["tension"]) if res["tension"] else 0.0
    # the safety factor multiplies the EXTERNAL part of the bolt tension only: the preload is a known, controlled load (clamp of a hand-tightened screw)
    Tpre = float(res.get("preload_n", 0.0))
    Tdem = Tpre / sf + max(Tmax - Tpre, 0.0) if sf > 0 else Tmax
    Vmax = max(res["shear"]) if res["shear"] else 0.0
    rows.append(Row(ins.id, case, cls, "insert_pullout", pull_cap / (sf * Tdem) if Tdem > 1e-9 else 1e9, Tmax, pull_cap, sf, "N", where,
                    "heat-set insert pulls out of its boss", gate, {"patch_pressure_mpa": res["patch_pressure_max_mpa"], "net_axial_n": res["net_axial_n"],
                                                                 "moment_nmm": res["moment_nmm"], "orientation_factor": orient}))
    # screw head pull-through on the screw part
    t_s = _thickness(scr.mesh, con.bolts[0]["screw_site"].p if con.bolts[0]["screw_site"] else con.centroid, -con.d, _perp(con.d, HEAD_D.get(th, 5.5) / 2 + 1.0))
    cb = LOW_CB_DEPTH.get(th, 2.3)
    t_floor = max((t_s - cb) if np.isfinite(t_s) else 1.6, 0.8)
    D_h, d_h = HEAD_D.get(th, 5.5), HOLE_D.get(th, 3.4)
    wsh = (scr.meta or {}).get("screw_washer_od_mm") or {}
    if isinstance(wsh, dict) and th in wsh:
        D_h = float(wsh[th])                                           # builder: screw_clearance(washer_od=...) recorded on the part
    punch = math.pi * D_h * t_floor * shear_allow(m_s, con.d, scr.print_up)
    head_area = math.pi / 4.0 * (D_h ** 2 - d_h ** 2)
    cap_h = min(m_s.tensile(90.0) * head_area, punch)
    rows.append(Row(scr.id, case, cls, "screw_head_pull_through", cap_h / (sf * Tdem) if Tdem > 1e-9 else 1e9, Tmax, cap_h, sf, "N", where + f", floor {t_floor:.1f} mm",
                    "screw head pulls through the counterbore floor", gate))
    cap_scr = SCREW_YIELD * THREAD_AREA.get(th, 5.03)
    rows.append(Row(scr.id, case, cls, "screw_tension", cap_scr / (sf * max(Tdem, 1e-9)), Tmax, cap_scr, sf, "N", where, "steel screw yields in tension", gate))
    # shear: bearing in the clearance hole + tear-out in both parts
    L = con.bolts[0]["length"]
    t_hole = max(L - INSERT_LEN.get(th, 5.7) + 1.0, t_s if np.isfinite(t_s) else 2.0)
    d_s = SHANK_D.get(th, 3.0)
    sig = Vmax / (d_s * t_hole)
    allow_br = m_s.bearing(90.0)
    rows.append(Row(scr.id, case, cls, "screw_bearing", allow_br / (sf * sig) if sig > 1e-9 else 1e9, sig, allow_br, sf, "MPa", where + f", shank {t_hole:.1f} mm in the part",
                    "screw bears on the clearance hole", gate, {"V_max_n": Vmax}))
    for part, mat, ed_list, label in ((scr, m_s, con.edge_dist, "screw part"), (ins, m_i, con.edge_dist_ins, "insert part")):
        e = min(ed_list) if ed_list else float("inf")
        lig = max(e - d_h / 2.0, 0.1)
        t_eff = t_hole if label == "screw part" else INSERT_LEN.get(th, 5.7)
        cap = 2.0 * lig * t_eff * shear_allow(mat, con.d, part.print_up)
        rows.append(Row(part.id, case, cls, "screw_tear_out", cap / (sf * Vmax) if Vmax > 1e-9 else 1e9, Vmax, cap, sf, "N", where + f", ligament {lig:.1f} mm ({label})",
                        "bolt tears out through the free edge", gate))
    return rows


def bearing_seat_check(model: Model, j: JointRec, part: PartRec, pl: PartLoads, case: str, cls: str) -> list[Row]:
    sf, _fat, gate = sf_of(cls)
    rb = [ld for ld in pl.loads if ld.label.startswith("idler bearing reaction")]
    if not rb or not j.idler_bearing:
        return []
    R = float(np.linalg.norm(sum((ld.F for ld in rb), np.zeros(3))))
    od, w = BEARING_OD.get(j.idler_bearing, 10.0), BEARING_W.get(j.idler_bearing, 4.0)
    mat = get_material(part.material)
    a = j.servo_z / np.linalg.norm(j.servo_z)
    c = rb[0].point
    p_br = R / (od * w)
    allow = mat.bearing(90.0)
    rows = [Row(part.id, case, cls, "bearing_seat_pressure", allow / (sf * p_br) if p_br > 1e-9 else 1e9, p_br, allow, sf, "MPa", f"{j.name}: {j.idler_bearing} in the idler plate",
                "bearing crushes the seat wall", gate)]
    sec = section_geometry(part.mesh, c, a)
    if sec is not None:
        geom = sec[0]
        poly = geom if geom.geom_type == "Polygon" else max(geom.geoms, key=lambda q: q.area)
        lig = max(Point(0, 0).distance(poly.exterior) - od / 2.0 - 0.05, 0.1)
        cap = 2.0 * lig * w * shear_allow(mat, a, part.print_up)
        rows.append(Row(part.id, case, cls, "bearing_seat_ligament", cap / (sf * R) if R > 1e-9 else 1e9, R, cap, sf, "N",
                        f"{j.name}: ligament {lig:.1f} mm around the bearing seat", "seat wall shears out toward the plate edge", gate))
    return rows


def clamp_checks(model: Model, topo: Topology, part: PartRec) -> list[Row]:
    """Assembly: the clamp force of a hand-tightened screw against the insert pull-out and the counterbore floor."""
    hdl = policy()["handling"]["screw_clamp_force_n"]
    sf = float(hdl.get("sf", 1.0))
    rows = []
    for s in part.sites:
        th = s.thread
        if th not in hdl:
            continue
        F = float(hdl[th])
        mat = get_material(part.material)
        if s.kind == "insert":
            ref = get_material(policy()["fasteners"]["insert_ref_material"])
            cap = float(policy()["fasteners"]["insert_pullout_n"][th]["v"]) * mat.tensile(90.0) / ref.tensile(90.0) * (mat.tensile(phi_deg(s.z, part.print_up)) / mat.tensile(90.0))
            rows.append(Row(part.id, f"assembly_clamp_{s.id}", "handling", "insert_pullout_clamp", cap / (sf * F), F, cap, sf, "N", f"{s.id} ({th})",
                            "insert pulls out while tightening", True))
    # one row per part: the worst
    if not rows:
        return []
    w = min(rows, key=lambda r: r.margin)
    w.case = "assembly_clamp"
    return [w]
