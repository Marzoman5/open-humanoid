"""M3 worker: runs INSIDE the Blender-as-a-module virtualenv (`pip install bpy==5.0.1`, which pins numpy 1.26 and so cannot
share the main venv). Reads the LegSpec JSON, writes STL files. Imports nothing from openhumanoid.

    .venv-bpy/Scripts/python m3_bpy_worker.py spec.json out_dir [comp.json] [--outer-only]

Pipeline per segment: low-poly cage (a ring of 16 vertices per profile station, n-gon end caps) -> Subdivision Surface
(Catmull-Clark, 3 levels) -> [shank: Boolean-difference the knee-pocket cutter] -> Solidify (inward, even thickness)
-> Boolean-difference the inflated keep-outs -> Boolean-difference the reveal-gap slab -> STL. Units: 1 Blender unit = 1 mm.
`comp.json` holds per-station (width, depth) multipliers that pre-compensate the shrink of subdivision.
"""
import json
import math
import sys

import bpy  # noqa: E402  (must come first: bmesh only exists after bpy is imported)
import bmesh  # noqa: E402

RING = 16
LEVELS = 3


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_obj(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def recalc(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def apply_mod(ob, mod):
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def cage(name, stations, comp):
    verts, faces = [], []
    for i, (z, w, d, n, cx) in enumerate(stations):
        cw, cd = comp[i] if comp else (1.0, 1.0)
        ring = []
        for k in range(RING):
            t = 2 * math.pi * k / RING
            c, s = math.cos(t), math.sin(t)
            x = cx + cd * d / 2 * math.copysign(abs(c) ** (2 / n), c)
            y = cw * w / 2 * math.copysign(abs(s) ** (2 / n), s)
            ring.append(len(verts))
            verts.append((x, y, z))
        if i:
            prev = list(range(len(verts) - 2 * RING, len(verts) - RING))
            for k in range(RING):
                a, b = prev[k], prev[(k + 1) % RING]
                c_, d_ = ring[(k + 1) % RING], ring[k]
                faces.append((a, b, c_, d_))
    n_st = len(stations)
    faces.append(tuple(reversed(range(RING))))                    # bottom cap
    faces.append(tuple(range((n_st - 1) * RING, n_st * RING)))   # top cap
    ob = make_obj(name, verts, faces)
    recalc(ob)
    return ob


def subsurf(ob, levels=LEVELS):
    m = ob.modifiers.new("sub", "SUBSURF")
    m.subdivision_type = "CATMULL_CLARK"
    m.levels = levels
    m.render_levels = levels
    apply_mod(ob, m)


def boolean_diff(ob, other):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.object = other
    m.solver = "MANIFOLD"
    apply_mod(ob, m)


def solidify(ob, t):
    m = ob.modifiers.new("solid", "SOLIDIFY")
    m.thickness = t
    m.offset = -1.0
    m.use_even_offset = True
    apply_mod(ob, m)


def prism(name, poly, half_y=80.0):
    n = len(poly)
    verts = [(x, -half_y, z) for x, z in poly] + [(x, half_y, z) for x, z in poly]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, n + i, n + j, j))
    ob = make_obj(name, verts, faces)
    recalc(ob)
    return ob


def box_obj(name, centre, size):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        v.co.x += centre[0]; v.co.y += centre[1]; v.co.z += centre[2]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def capsule_objs(name, p0, p1, r):
    out = []
    z0, z1 = sorted((p0[2], p1[2]))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r, depth=z1 - z0)
    for v in bm.verts:
        v.co.x += p0[0]; v.co.y += p0[1]; v.co.z += (z0 + z1) / 2
    me = bpy.data.meshes.new(name + "_c"); bm.to_mesh(me); bm.free()
    out.append(bpy.data.objects.new(name + "_c", me))
    for k, z in enumerate((z0, z1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
        for v in bm.verts:
            v.co.x += p0[0]; v.co.y += p0[1]; v.co.z += z
        me = bpy.data.meshes.new(f"{name}_s{k}"); bm.to_mesh(me); bm.free()
        out.append(bpy.data.objects.new(f"{name}_s{k}", me))
    for o in out:
        bpy.context.scene.collection.objects.link(o)
    return out


def export_stl(ob, path):
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0, apply_modifiers=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    outer_only = "--outer-only" in sys.argv
    spec = json.load(open(args[0]))
    out = args[1]
    comp = json.load(open(args[2])) if len(args) > 2 else {}
    p = spec["params"]
    for seg in ("thigh", "shank"):
        reset()
        st = spec[f"{seg}_stations"]
        ob = cage(seg, st, comp.get(seg))
        subsurf(ob)
        if outer_only:
            export_stl(ob, f"{out}/{seg}_outer.stl")
            continue
        if seg == "shank":
            boolean_diff(ob, prism("cutter", spec["cutter_outer"]))
        solidify(ob, p["wall"])
        for k in spec["keepouts"]:
            if k["host"] != seg:
                continue
            if k["kind"] == "box":
                size = [s + 2 * p["clearance"] for s in k["size"]]
                boolean_diff(ob, box_obj(k["name"], k["center"], size))
            else:
                for c in capsule_objs(k["name"], k["p0"], k["p1"], k["radius"] + p["clearance"]):
                    boolean_diff(ob, c)
        boolean_diff(ob, box_obj("seam", (p["seam_x"], 0, 0), (p["seam_gap"], 400, 600)))
        export_stl(ob, f"{out}/{seg}.stl")


main()
