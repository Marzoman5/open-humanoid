"""Write a build123d link tree to the CAD export contract (cad/EXPORT_CONTRACT.md), plus checks.

Generic: takes any `dict[str, Link]` (from a template or a hand-written variant model) and produces
parts/*.step|stl, meshes/<link>.stl (+ per-colour visual meshes), mass_properties.yaml, robot.xml, manifest.yaml.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
from pathlib import Path

import build123d as bd
import yaml

from .. import simgen
from ..paths import repo_root
from ..spec import expand_joints
from .geom import Link, Part, box_mass_properties, combine_mass, fits_bed, interference, mass_properties

CONTRACT_VERSION = "0.1"
MESH_TOL = {"tolerance": 0.1, "angular_tolerance": 0.25}


def compound(shapes: list[bd.Shape]) -> bd.Shape:
    return shapes[0] if len(shapes) == 1 else bd.Compound(children=list(shapes))


def part_mass(p: Part, style: dict) -> dict:
    if p.material == "purchased":
        return box_mass_properties(p.shape, p.mass_kg or 0.0)
    rho = style["densities_kg_m3"].get(p.material, 1240) * style["fill_fraction"].get(p.kind, 1.0)
    return mass_properties(p.shape, rho)


def link_masses(links: dict[str, Link], style: dict, extra: dict[str, list[dict]] | None = None) -> dict[str, dict]:
    """Per-link mass, COM (m) and inertia (kg·m² about COM), plus a printed/purchased split."""
    out = {}
    for name, L in links.items():
        items, printed, bought = [], 0.0, 0.0
        for p in L.parts:
            mp = part_mass(p, style)
            items.append(mp)
            if p.material == "purchased":
                bought += mp["mass"]
            else:
                printed += mp["mass"]
        items += (extra or {}).get(name, [])
        bought += sum(e["mass"] for e in (extra or {}).get(name, []))
        mp = combine_mass(items)
        if mp["mass"] < 1e-4:   # massless intermediate link: tiny regular inertia keeps the sim valid
            mp = {"mass": 1e-4, "com": [0.0, 0.0, 0.0], "inertia": [[1e-8, 0, 0], [0, 1e-8, 0], [0, 0, 1e-8]]}
        mp["printed_kg"], mp["purchased_kg"] = printed, bought
        out[name] = mp
    return out


# --------------------------------------------------------------------------- kinematics


def world_locations(links: dict[str, Link], q: dict[str, float]) -> dict[str, bd.Location]:
    """Forward kinematics at joint angles q (rad). Links must be ordered parents-first."""
    import math

    locs: dict[str, bd.Location] = {}
    for name, L in links.items():
        loc = (locs[L.parent] if L.parent else bd.Location()) * bd.Pos(*L.pos_mm) * bd.Rot(*L.rot_deg)
        for j in L.joints:
            a = math.degrees(q.get(j["name"], 0.0))
            loc = loc * bd.Rot(*(a if ax == j["axis"] else 0 for ax in "xyz"))
        locs[name] = loc
    return locs


def check(links: dict[str, Link], q: dict[str, float], min_mm3: float = 20.0, bed_mm=None) -> dict:
    """Interference between parts at pose q (pairs touching by design have zero volume), and bed fit of
    printed parts. Returns {'clashes': [(a, b, mm3)], 'unknown': [(a, b)] (OCC boolean failed),
    'oversize': [(id, extents)]}."""
    locs = world_locations(links, q)
    placed = [(n, p, locs[n] * p.shape) for n, L in links.items() for p in L.parts]
    clashes, unknown = [], []
    for i in range(len(placed)):
        for k in range(i + 1, len(placed)):
            (na, pa, sa), (nb, pb, sb) = placed[i], placed[k]
            if pa.kind == "shell" and pb.kind == "shell" and na == nb:
                continue
            v = interference(sa, sb)
            if v > min_mm3:
                clashes.append((pa.id, pb.id, round(v, 1)))
            elif v < 0:
                unknown.append((pa.id, pb.id))
    oversize = []
    if bed_mm:
        for _, p, _ in placed:
            if p.material != "purchased":
                ok, ext = fits_bed(p.shape, bed_mm)
                if not ok:
                    oversize.append((p.id, [round(e, 1) for e in ext]))
    return {"clashes": clashes, "unknown": unknown, "oversize": oversize}


# --------------------------------------------------------------------------- MJCF


def _fmt(v, nd=5):
    return " ".join(f"{x:.{nd}g}" if abs(x) > 1e-12 else "0" for x in v)


def mjcf(spec: dict, sizing: dict, links: dict[str, Link], masses: dict[str, dict], style: dict,
         mesh_files: dict[str, list[tuple[str, str]]]) -> str:
    """MJCF whose bodies are the CAD links. Visual meshes are coloured by part role; contact = soles."""
    joints = {j["name"]: j for j in expand_joints(spec, sizing["joints_base"])}
    acts = sizing["actuators"]
    colors = style["colors"]
    assets = [f'    <material name="{k}" rgba="{_fmt(v, 3)}" specular="{0.9 if k == "visor" else 0.25}" '
              f'shininess="{0.95 if k == "visor" else 0.3}" reflectance="{0.15 if k == "visor" else 0}"/>' for k, v in colors.items()]
    for files in mesh_files.values():
        for mname, f in files:
            assets.append(f'    <mesh name="{mname}" file="{f}" scale="0.001 0.001 0.001"/>')
    children: dict[str | None, list[str]] = {}
    for n, L in links.items():
        children.setdefault(L.parent, []).append(n)

    def body(n: str, ind: str) -> str:
        L, m = links[n], masses[n]
        pos = [v / 1000 for v in L.pos_mm]
        if L.parent is None:
            pos = [0, 0, simgen.stand_height(sizing, spec)]
        rot = f' euler="{_fmt(L.rot_deg)}"' if any(L.rot_deg) else ""
        lines = [f'{ind}<body name="{n}" pos="{_fmt(pos)}"{rot}>']
        if L.parent is None:
            lines += [f'{ind}  <freejoint name="root"/>', f'{ind}  <site name="imu" pos="0 0 0"/>']
        for j in L.joints:
            lines.append(simgen.joint_xml(joints[j["name"]], acts[j["name"]], ind + "  "))
        I = m["inertia"]
        lines.append(f'{ind}  <inertial pos="{_fmt(m["com"])}" mass="{m["mass"]:.5g}" '
                     f'fullinertia="{_fmt([I[0][0], I[1][1], I[2][2], I[0][1], I[0][2], I[1][2]])}"/>')
        for mname, _ in mesh_files.get(n, []):
            color = mname.split("__")[1]
            lines.append(f'{ind}  <geom type="mesh" mesh="{mname}" material="{color}" class="visual"/>')
        for p in L.parts:
            if p.kind == "sole":
                bb = p.shape.bounding_box()
                c = [(bb.min.X + bb.max.X) / 2000, (bb.min.Y + bb.max.Y) / 2000, (bb.min.Z + bb.max.Z) / 2000]
                s = [(bb.max.X - bb.min.X) / 2000, (bb.max.Y - bb.min.Y) / 2000, (bb.max.Z - bb.min.Z) / 2000]
                lines.append(f'{ind}  <geom name="{n}" type="box" pos="{_fmt(c)}" size="{_fmt(s)}" class="contact"/>')
                lines.append(f'{ind}  <site name="{n}" pos="{_fmt([c[0], c[1], bb.min.Z / 1000])}"/>')
        for ch in children.get(n, []):
            lines.append(body(ch, ind + "  "))
        lines.append(f"{ind}</body>")
        return "\n".join(lines)

    root = children[None][0]
    sim_joints = [joints[j["name"]] for L in links.values() for j in L.joints]
    return f"""<!-- GENERATED by `oh cad build {spec['id']}` from the CAD link tree. Do not edit by hand. -->
<mujoco model="{spec['id']}">
  <compiler angle="degree" autolimits="true" meshdir="meshes"/>
  <option timestep="{spec['sim'].get('timestep_s', 0.002)}" integrator="implicitfast"/>
  <default>
    <default class="visual"><geom contype="0" conaffinity="0" group="1"/></default>
    <default class="contact"><geom contype="1" conaffinity="1" friction="1.0 0.02 0.01" rgba="0.1 0.1 0.1 0" group="3"/></default>
  </default>
  <visual><global offwidth="1920" offheight="1200"/><headlight diffuse="0.45 0.45 0.45" ambient="0.25 0.25 0.25" specular="0.1 0.1 0.1"/><quality shadowsize="4096"/></visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.97 0.97 0.98" rgb2="0.80 0.81 0.84" width="512" height="512"/>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.86 0.86 0.88" rgb2="0.82 0.82 0.84" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="10 10" reflectance="0.05"/>
{chr(10).join(assets)}
  </asset>
  <worldbody>
    <light pos="0.6 0.8 1.6" dir="-0.35 -0.45 -1" directional="true" diffuse="0.55 0.55 0.55" castshadow="true"/>
    <light pos="-0.8 -0.4 1.2" dir="0.6 0.3 -0.8" directional="true" diffuse="0.25 0.25 0.27" castshadow="false"/>
    <geom name="floor" type="plane" size="0 0 0.05" material="grid" contype="1" conaffinity="1"/>
{body(root, '    ')}
  </worldbody>
  <actuator>
{chr(10).join(simgen.actuator_lines(sim_joints, acts))}
  </actuator>
  <sensor>
    <framequat name="imu_quat" objtype="site" objname="imu"/>
    <gyro name="imu_gyro" site="imu"/>
    <accelerometer name="imu_acc" site="imu"/>
{simgen.sensor_lines(sim_joints)}
  </sensor>
</mujoco>
"""


# --------------------------------------------------------------------------- contract writer


def _git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root(), capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root(), capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def lumped_extras(spec: dict, links: dict[str, Link], host: str = "torso") -> dict[str, list[dict]]:
    """Fixed BOM parts that have no CAD envelope (plus spec electronics_kg) as small boxes in `host`."""
    from .. import catalog

    placed = {p.catalog for L in links.values() for p in L.parts if p.catalog}
    items = []
    for it in spec["bom"].get("fixed", []):
        if it["part"] in placed:
            continue
        m = catalog.get(it["part"]).get("mass_kg", 0.0) * it.get("qty", 1)
        if m:
            items.append(m)
    items.append(spec["mass_model"].get("electronics_kg", 0.0))
    L = links[host]
    zs = [p.shape.bounding_box() for p in L.parts if p.kind == "frame"]
    zc = (min(b.min.Z for b in zs) + max(b.max.Z for b in zs)) / 2000 if zs else 0.0
    m = sum(items)
    s = 0.04
    return {host: [{"mass": m, "com": [0.0, 0.0, zc], "inertia": [[m * s * s / 6, 0, 0], [0, m * s * s / 6, 0], [0, 0, m * s * s / 6]]}]}


def export(spec: dict, sizing: dict, links: dict[str, Link], style: dict, out_dir: Path, notes: list[str] | None = None,
           backend: str = "build123d") -> dict:
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "parts").mkdir(parents=True)
    (out_dir / "meshes").mkdir()
    extras = lumped_extras(spec, links)
    masses = link_masses(links, style, extras)

    # parts: one STEP per unique printed part, one per purchased catalog part (envelope); STL for printed.
    manifest_parts, purchased = [], {}
    for L in links.values():
        for p in L.parts:
            if p.kind == "horn":
                continue
            if p.material == "purchased":
                key = p.catalog or p.id
                if key not in purchased:
                    bd.export_step(p.shape, str(out_dir / "parts" / f"{key}.step"))
                    purchased[key] = {"id": key, "qty": 0, "process": "purchased", "material": "purchased", "catalog": key}
                purchased[key]["qty"] += 1
                continue
            bd.export_step(p.shape, str(out_dir / "parts" / f"{p.id}.step"))
            bd.export_stl(p.shape, str(out_dir / "parts" / f"{p.id}.stl"), **MESH_TOL)
            mp = part_mass(p, style)
            manifest_parts.append({"id": p.id, "qty": 1, "process": "fdm", "material": p.material, "link": L.name,
                                   "mass_kg": round(mp["mass"], 4), "print": {"orientation": "as_exported", **p.print}})

    # meshes: one per link (contract) + one per colour group (render)
    mesh_files: dict[str, list[tuple[str, str]]] = {}
    for n, L in links.items():
        if not L.parts:
            continue
        bd.export_stl(compound([p.shape for p in L.parts]), str(out_dir / "meshes" / f"{n}.stl"), **MESH_TOL)
        groups: dict[str, list] = {}
        for p in L.parts:
            groups.setdefault(p.color, []).append(p.shape)
        for color, shapes in groups.items():
            f = f"{n}__{color}.stl"
            bd.export_stl(compound(shapes), str(out_dir / "meshes" / f), **MESH_TOL)
            mesh_files.setdefault(n, []).append((f"{n}__{color}", f))

    mp_yaml = {"units": {"mass": "kg", "length": "m", "inertia": "kg*m^2 about COM, link frame"}, "links": {
        n: {"mass": round(m["mass"], 5), "com": [round(v, 5) for v in m["com"]],
            "inertia": [[round(v, 9) for v in row] for row in m["inertia"]],
            "printed_kg": round(m["printed_kg"], 4), "purchased_kg": round(m["purchased_kg"], 4)} for n, m in masses.items()}}
    (out_dir / "mass_properties.yaml").write_text(yaml.safe_dump(mp_yaml, sort_keys=False), encoding="utf-8")
    (out_dir / "robot.xml").write_text(mjcf(spec, sizing, links, masses, style, mesh_files), encoding="utf-8")

    totals = {"printed_kg": round(sum(m["printed_kg"] for m in masses.values()), 4),
              "purchased_kg": round(sum(m["purchased_kg"] for m in masses.values()), 4)}
    totals["total_kg"] = round(totals["printed_kg"] + totals["purchased_kg"], 4)
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "source": {"backend": backend, "location": spec.get("cad", {}).get("source", f"variants/{spec['id']}/cad/"),
                   "template": spec["kinematics"].get("template"), "version": _git_version()},
        "units": {"step": "mm", "mesh": "mm"},
        "exported": _dt.date.today().isoformat(),
        "height_m": sizing["height_m"],
        "totals": totals,
        "notes": notes or [],
        "parts": manifest_parts + list(purchased.values()),
    }
    (out_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {"dir": str(out_dir), "totals": totals, "printed_parts": len(manifest_parts), "masses": masses}
