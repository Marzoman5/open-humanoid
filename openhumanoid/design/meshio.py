"""Load a 'subject' (mesh set, profiles file, or variant CAD export) into named parts in the design frame
(metres, z up, x forward, y left, feet on z=0, body centred on x=y=0)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Subject:
    name: str
    parts: dict          # part name -> trimesh.Trimesh (design frame, normalised)
    height_m: float
    profiles: dict | None = None
    joints: dict = field(default_factory=dict)       # joint id -> (x,y,z)
    hard_points: list = field(default_factory=list)  # from profiles
    source: str = ""
    classes: dict = field(default_factory=dict)      # part name -> 'shell' | 'hardware' (for S5)
    whole: object = None                              # single watertight mesh when the subject is a profile massing

    @property
    def render_meshes(self) -> dict:
        return {self.name: self.whole} if self.whole is not None else self.parts

    @property
    def mesh(self):
        import trimesh
        return self.whole if self.whole is not None else trimesh.util.concatenate(list(self.parts.values()))


HARDWARE_TOKENS = ("__servo", "__frame", "__horn", "__cable", "_servo", "_frame", "_horn")


def classify(part_name: str) -> str:
    return "hardware" if any(t in part_name for t in HARDWARE_TOKENS) else "shell"


def normalise(parts: dict, joints: dict | None = None):
    """Put feet on z=0 and centre the bounding box on x=y=0. Returns (parts, joints, shift)."""
    lo = np.min([m.bounds[0] for m in parts.values()], axis=0)
    hi = np.max([m.bounds[1] for m in parts.values()], axis=0)
    shift = np.array([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    out = {}
    for k, m in parts.items():
        m = m.copy()
        m.apply_translation(shift)
        out[k] = m
    jn = {k: tuple(np.array(v) + shift) for k, v in (joints or {}).items()}
    return out, jn, shift


def from_profiles(path: str | Path, voxel_m: float | None = None) -> Subject:
    from .massing import build_massing, split_by_label
    from .profiles import load_profiles

    prof = load_profiles(path)
    mesh, labels = build_massing(prof, voxel_m)
    parts = split_by_label(mesh, labels)
    # the massing is already in the profile frame (feet on z=0); do not re-centre so hard points stay valid
    joints = {j["id"]: tuple(j["pos"]) for j in prof.get("joints", [])}
    return Subject(prof.get("name", Path(path).stem), parts, prof["height_m"], prof, joints,
                   prof.get("hard_points", []), f"profiles:{path}", {k: "shell" for k in parts}, mesh)


def from_meshes(paths: list[Path], name: str, up: str = "z", scale: float | None = None) -> Subject:
    """STL / GLB / OBJ / PLY files (or a GLB scene). Units guessed: if the height > 5 the file is taken to be in mm."""
    import trimesh

    parts: dict = {}
    for p in paths:
        loaded = trimesh.load(str(p))
        if isinstance(loaded, trimesh.Scene):
            for gname, g in loaded.geometry.items():
                try:
                    g = g.copy(); g.apply_transform(loaded.graph.get(gname)[0])
                except Exception:
                    pass
                parts[f"{p.stem}:{gname}"] = g
        else:
            parts[p.stem] = loaded
    parts = {k: v for k, v in parts.items() if hasattr(v, "faces") and len(v.faces)}
    if not parts:
        raise ValueError("no triangle meshes found")
    if up == "y":
        rot = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        for m in parts.values():
            m.apply_transform(rot)
    ext = np.max([m.bounds[1][2] for m in parts.values()]) - np.min([m.bounds[0][2] for m in parts.values()])
    s = scale if scale is not None else (0.001 if ext > 5 else 1.0)
    if s != 1.0:
        for m in parts.values():
            m.apply_scale(s)
    parts, _, _ = normalise(parts)
    H = float(np.max([m.bounds[1][2] for m in parts.values()]))
    return Subject(name, parts, H, None, {}, [], f"meshes:{len(paths)} files", {k: classify(k) for k in parts})


def from_mjcf(xml_path: str | Path, name: str, qpos: dict | None = None, visual_groups=(1,)) -> Subject:
    """Assemble the visual geoms of an MJCF (e.g. variants/<id>/cad/export/robot.xml) in the neutral pose (all qpos 0).
    Part names come from the mesh asset names, so '__frame' / '__servo' parts are classified as hardware."""
    import mujoco
    import trimesh

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(model)
    for jn, q in (qpos or {}).items():
        data.joint(jn).qpos[0] = q
    mujoco.mj_forward(model, data)
    parts: dict = {}
    for gi in range(model.ngeom):
        if model.geom_type[gi] != mujoco.mjtGeom.mjGEOM_MESH or int(model.geom_group[gi]) not in visual_groups:
            continue
        mid = model.geom_dataid[gi]
        v0, nv = model.mesh_vertadr[mid], model.mesh_vertnum[mid]
        f0, nf = model.mesh_faceadr[mid], model.mesh_facenum[mid]
        verts = model.mesh_vert[v0:v0 + nv].reshape(-1, 3)
        faces = model.mesh_face[f0:f0 + nf].reshape(-1, 3)
        R = data.geom_xmat[gi].reshape(3, 3)
        w = verts @ R.T + data.geom_xpos[gi]
        pname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MESH, mid) or f"mesh{mid}"
        parts[pname] = trimesh.Trimesh(w, faces, process=False)
    joints = {}
    for ji in range(model.njnt):
        jname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, ji)
        if jname:
            joints[jname] = tuple(data.xanchor[ji])
    parts, joints, _ = normalise(parts, joints)
    H = float(np.max([m.bounds[1][2] for m in parts.values()]))
    return Subject(name, parts, H, None, joints, [], f"mjcf:{xml_path}", {k: classify(k) for k in parts})


def load_subject(src: str | Path, name: str | None = None, voxel_m: float | None = None) -> Subject:
    """Dispatch on what `src` is: profiles .yaml, an .xml MJCF, a mesh file, or a directory of meshes."""
    src = Path(src)
    name = name or src.stem
    if src.suffix in (".yaml", ".yml"):
        return from_profiles(src, voxel_m)
    if src.suffix == ".xml":
        return from_mjcf(src, name)
    if src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in (".stl", ".glb", ".gltf", ".obj", ".ply"))
        return from_meshes(files, name)
    return from_meshes([src], name)
