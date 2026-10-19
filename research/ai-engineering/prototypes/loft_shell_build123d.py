import sys, math; from build123d import *
out=sys.argv[1]
def section(z,w,d,n,y0=0.0):
    pts=[]
    for i in range(16):
        a=2*math.pi*i/16; c,s=math.cos(a),math.sin(a)
        pts.append(Vector(w/2*math.copysign(abs(c)**(2/n),c), d/2*math.copysign(abs(s)**(2/n),s)+y0, z))
    return Wire([Spline(*pts, periodic=True)])
spec=[(0,46,40,3.2,0),(-30,44,42,3.0,2),(-70,36,36,2.8,1.5),(-110,30,30,2.6,0)]
outer=Solid.make_loft([section(z,w,d,n,y) for z,w,d,n,y in spec])
# A: offset with openings
A=offset(outer, amount=-1.6, openings=[outer.faces().sort_by(Axis.Z)[0], outer.faces().sort_by(Axis.Z)[-1]])
print("A offset:", type(A).__name__, "solids", len(A.solids()), "valid", A.is_valid, round(A.volume/1e3,2))
# B: outer minus inner loft (inner sections shrunk by 2*t), extended past ends
t=1.6
inner=Solid.make_loft([section(z+(1 if i==0 else -1 if i==len(spec)-1 else 0),w-2*t,d-2*t,n,y) for i,(z,w,d,n,y) in enumerate(spec)])
B=outer-inner
print("B subtract:", "valid", B.is_valid, round(B.volume/1e3,2))
for keep in (Keep.TOP, Keep.BOTTOM):
    h=split(B, bisect_by=Plane.YZ, keep=keep); print(" half", keep, h.is_valid, round(h.volume/1e3,2))
export_stl(B, out+"/thigh_B.stl"); export_step(B, out+"/thigh_B.step")
r=import_step(out+"/thigh_B.step"); print("B reimport", r.is_valid, round(r.volume/1e3,2))
import trimesh; m=trimesh.load(out+"/thigh_B.stl"); print("STL watertight", m.is_watertight, "faces", len(m.faces))
