# Prototype: (1) SDF smooth-union shell via manifold3d.level_set, (2) clay + silhouette render via pyvista.
import sys, time, math
import numpy as np
out = sys.argv[1]
import manifold3d as mf

def smin(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25

def capsule(p, a, b, ra, rb):
    """Tapered capsule (round cone approx) from a (radius ra) to b (radius rb)."""
    pa = np.subtract(p, a); ba = np.subtract(b, a)
    t = max(0.0, min(1.0, float(np.dot(pa, ba) / np.dot(ba, ba))))
    r = ra + (rb - ra) * t
    return float(np.linalg.norm(pa - ba * t)) - r

def ellipsoid(p, c, r):
    q = np.subtract(p, c) / r
    k0 = np.linalg.norm(q); k1 = np.linalg.norm(q / r)
    return float(k0 * (k0 - 1.0) / k1) if k1 > 0 else -min(r)

def head_neck(p):
    head = ellipsoid(p, (0, 0, 62), np.array([24.0, 27.0, 32.0]))
    neck = capsule(p, (0, 0, 0), (0, 0, 40), 13.0, 11.0)
    collar = ellipsoid(p, (0, 0, 2), np.array([30.0, 24.0, 8.0]))
    d = smin(smin(head, neck, 10.0), collar, 8.0)
    return d

T = 1.6  # wall
def shell_sdf(p):
    d = head_neck(p)
    return -(abs(d + T / 2) - T / 2)  # manifold level_set: positive = inside

t0 = time.time()
solid = mf.Manifold.level_set(lambda x, y, z: -head_neck((x, y, z)), [-40, -40, -12, 40, 40, 100], 1.0)
shell = mf.Manifold.level_set(lambda x, y, z: shell_sdf((x, y, z)), [-40, -40, -12, 40, 40, 100], 0.8)
# open the bottom so it slides over the frame
shell = shell - mf.Manifold.cube([100, 100, 10]).translate([-50, -50, -15])
print("level_set solid vol", round(solid.volume() / 1e3, 1), "cm3; shell vol", round(shell.volume() / 1e3, 2),
      "cm3; genus", shell.genus(), "; status", shell.status(), f"; {time.time()-t0:.1f}s")
m = shell.to_mesh()
verts = np.asarray(m.vert_properties)[:, :3]; faces = np.asarray(m.tri_verts)
import trimesh
tm = trimesh.Trimesh(verts, faces)
print("trimesh watertight", tm.is_watertight, "faces", len(faces))
tm.export(out + "/head_shell.stl")

# Render: clay (lit, SSAO) + orthographic silhouette, for both parts
import pyvista as pv
pv.OFF_SCREEN = True
thigh = pv.read(out + "/thigh_B.stl")
head = pv.read(out + "/head_shell.stl").translate((90, 0, -60))
for name, style in (("clay", "clay"), ("silhouette", "sil")):
    pl = pv.Plotter(off_screen=True, window_size=(900, 700))
    pl.set_background("white")
    for mesh in (thigh, head):
        if style == "clay":
            pl.add_mesh(mesh, color="#d9d6cf", smooth_shading=True, specular=0.25, specular_power=20)
        else:
            pl.add_mesh(mesh, color="black", lighting=False)
    if style == "clay":
        pl.enable_ssao(radius=4)
    pl.camera_position = [(260, -420, 60), (45, 0, -40), (0, 0, 1)]
    if style == "sil":
        pl.enable_parallel_projection()
        pl.camera_position = [(45, -800, -30), (45, 0, -30), (0, 0, 1)]
    pl.screenshot(out + f"/proto_{name}.png")
    pl.close()
print(f"rendered in {time.time()-t0:.1f}s")
