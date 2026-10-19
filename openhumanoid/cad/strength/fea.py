"""Linear-elastic FEA of one printed part with scikit-fem on a gmsh tetrahedral mesh (research C7).

* Mesh: gmsh (OpenCASCADE kernel) from the part's STEP (fallback: the part's surface mesh), first-order tets, size field = a global size
  plus a fine zone around the analytic hot spot and every internal corner (sharp edges and fillets from corners.py).
* Elements: quadratic tets (P2 displacement), so bending is accurate on coarse meshes.
* Material: transversely isotropic, the symmetry axis is the build direction. In-plane E from the datasheet XY value, E along the build
  direction from the Z value; shear modulus and Poisson ratio are assumptions (policy `fea`).
* Loads: the point forces / moments the load path puts on the part (equilibrated with the reaction), each distributed over the surface nodes
  within a patch (a rigid-body-consistent force + couple distribution), plus self weight; 3-2-1 supports on three load nodes (reaction ~ 0).
* Result: failure index per quadrature point from the weakest-direction rule (delamination: build-direction normal stress + interlayer shear
  against the Z allowable; in-plane: principal / von Mises against the XY allowable), peak and the mean of the worst 1% of elements.
  Convergence: `converge()` runs two mesh densities and reports the change in peak.
"""
from __future__ import annotations

import math
import os
import tempfile
import time
from dataclasses import dataclass, field

import numpy as np

from .loadpath import Load, PartLoads
from .model import PartRec
from .policy import material as get_material, policy, pv


# ------------------------------------------------------------------------------------------------------------------- meshing
def tet_mesh(part: PartRec, h: float, fine_pts: list[tuple[np.ndarray, float, float]] | None = None, h_min: float | None = None, verbose: bool = False):
    """(points (N,3), tets (M,4)) of `part`. `fine_pts`: [(centre, radius, size)] refinement balls."""
    import gmsh

    fine_pts = fine_pts or []
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
        gmsh.model.add("part")
        with tempfile.TemporaryDirectory() as td:
            if part.step:
                fp = os.path.join(td, "p.step")
                open(fp, "wb").write(part.step)
                gmsh.model.occ.importShapes(fp)
                gmsh.model.occ.synchronize()
            else:
                import math as _m

                fp = os.path.join(td, "p.stl")
                part.mesh.export(fp)
                gmsh.merge(fp)
                gmsh.model.mesh.classifySurfaces(_m.radians(35), True, True)
                gmsh.model.mesh.createGeometry()
                surfs = gmsh.model.getEntities(2)
                loop = gmsh.model.geo.addSurfaceLoop([s[1] for s in surfs])
                gmsh.model.geo.addVolume([loop])
                gmsh.model.geo.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", h)
        gmsh.option.setNumber("Mesh.MeshSizeMin", h_min or h / 5.0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        fids = []
        for i, (c, r, sz) in enumerate(fine_pts):
            f = gmsh.model.mesh.field.add("Ball")
            gmsh.model.mesh.field.setNumber(f, "XCenter", float(c[0]))
            gmsh.model.mesh.field.setNumber(f, "YCenter", float(c[1]))
            gmsh.model.mesh.field.setNumber(f, "ZCenter", float(c[2]))
            gmsh.model.mesh.field.setNumber(f, "Radius", float(r))
            gmsh.model.mesh.field.setNumber(f, "Thickness", float(r))
            gmsh.model.mesh.field.setNumber(f, "VIn", float(sz))
            gmsh.model.mesh.field.setNumber(f, "VOut", float(h))
            fids.append(f)
        if fids:
            m = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(m, "FieldsList", fids)
            gmsh.model.mesh.field.setAsBackgroundMesh(m)
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.model.mesh.generate(3)
        tags, coords, _ = gmsh.model.mesh.getNodes()
        coords = np.asarray(coords).reshape(-1, 3)
        idx = {int(t): i for i, t in enumerate(tags)}
        et, _, en = gmsh.model.mesh.getElements(3)
        tets = None
        for t, nodes in zip(et, en):
            if t == 4:
                tets = np.array([idx[int(x)] for x in nodes]).reshape(-1, 4)
        if tets is None:
            raise RuntimeError("gmsh produced no tetrahedra")
        used = np.unique(tets)
        remap = -np.ones(len(coords), int)
        remap[used] = np.arange(len(used))
        return coords[used], remap[tets]
    finally:
        gmsh.finalize()


def _linear_solve(Kc, b, basis, I) -> np.ndarray:
    """Direct LU for small systems, smoothed-aggregation AMG + CG (rigid-body near-null space) for large ones."""
    from scipy.sparse.linalg import spsolve

    if Kc.shape[0] < 40000:
        return spsolve(Kc, b)
    import pyamg

    N = basis.N
    comp = np.zeros(N, int)
    for r in range(3):
        comp[basis.nodal_dofs[r]] = r
        if basis.edge_dofs is not None and basis.edge_dofs.size:
            comp[basis.edge_dofs[r]] = r
    X = np.asarray(basis.doflocs).T            # (N, 3)
    B = np.zeros((N, 6))
    for k in range(3):
        B[comp == k, k] = 1.0
    # rotations about x, y, z: omega x r
    B[comp == 1, 3] = -X[comp == 1, 2]; B[comp == 2, 3] = X[comp == 2, 1]
    B[comp == 0, 4] = X[comp == 0, 2];  B[comp == 2, 4] = -X[comp == 2, 0]
    B[comp == 0, 5] = -X[comp == 0, 1]; B[comp == 1, 5] = X[comp == 1, 0]
    ml = pyamg.smoothed_aggregation_solver(Kc, B=B[I], max_coarse=500)
    resid = []
    xs = ml.solve(b, tol=1e-9, accel="cg", maxiter=400, residuals=resid)
    return xs


# ----------------------------------------------------------------------------------------------------------------- material
def stiffness_tensor(mat, up: np.ndarray, nu: float | None = None, G_over_E: float | None = None) -> np.ndarray:
    """4th-order stiffness C_ijkl (MPa) of a transversely isotropic solid with symmetry axis `up` (build direction)."""
    nu = nu or float(pv(policy(), "fea", "poisson"))
    E1, E3 = mat.E_xy, mat.E_z              # in-plane, build direction
    nu12 = nu
    G12 = E1 / (2 * (1 + nu12))
    G13 = 0.5 * E3 / (1 + nu)               # interlayer shear modulus (assumption: isotropic-like with E3)
    # compliance in material axes (1, 2 in plane; 3 along build)
    S = np.zeros((6, 6))
    S[0, 0] = S[1, 1] = 1 / E1
    S[2, 2] = 1 / E3
    S[0, 1] = S[1, 0] = -nu12 / E1
    S[0, 2] = S[2, 0] = S[1, 2] = S[2, 1] = -nu / E1
    S[3, 3] = S[4, 4] = 1 / G13
    S[5, 5] = 1 / G12
    Cv = np.linalg.inv(S)                   # Voigt order 11 22 33 23 13 12 (engineering shear)
    C = np.zeros((3, 3, 3, 3))
    vo = {(0, 0): 0, (1, 1): 1, (2, 2): 2, (1, 2): 3, (2, 1): 3, (0, 2): 4, (2, 0): 4, (0, 1): 5, (1, 0): 5}
    for (i, j), a in vo.items():
        for (k, l), b in vo.items():
            C[i, j, k, l] = Cv[a, b]
    # rotate: material axis 3 -> up
    z = up / np.linalg.norm(up)
    x = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.column_stack([x, y, z])          # columns = material axes in global coordinates
    return np.einsum("ia,jb,kc,ld,abcd->ijkl", R, R, R, R, C)


# ----------------------------------------------------------------------------------------------------------------- loads
def patch_nodes(points: np.ndarray, bnodes: np.ndarray, p: np.ndarray, r_min: float = 2.0, r_max: float = 8.0, n_min: int = 8) -> np.ndarray:
    d = np.linalg.norm(points[bnodes] - p, axis=1)
    r = r_min
    while r <= r_max:
        sel = bnodes[d <= r]
        if len(sel) >= n_min:
            return sel
        r *= 1.4
    order = np.argsort(d)[:n_min]
    return bnodes[order]


def select_nodes(points: np.ndarray, bnodes: np.ndarray, ld: Load, patch_r: float) -> np.ndarray:
    sp_ = ld.patch or {"type": "sphere", "r": patch_r}
    X = points[bnodes]
    if sp_["type"] == "annulus":
        c, ax = np.asarray(sp_["c"]), np.asarray(sp_["axis"])
        rel = X - c
        along = rel @ ax
        rad = np.linalg.norm(rel - np.outer(along, ax), axis=1)
        sel = bnodes[(rad >= sp_["r0"]) & (rad <= sp_["r1"]) & (np.abs(along) <= sp_["half"] + (sp_.get("shift", 0.0)))]
        if len(sel) >= 6:
            return sel
    elif sp_["type"] == "sites":
        pts_ = [np.asarray(q) for q in sp_["points"]]
        sel = np.unique(np.concatenate([bnodes[np.linalg.norm(X - q, axis=1) <= sp_["r"]] for q in pts_]))
        if len(sel) >= 6:
            return sel
    return patch_nodes(points, bnodes, ld.point, r_min=float(sp_.get("r", patch_r)))


def distribute(points: np.ndarray, nodes: np.ndarray, p: np.ndarray, F: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Nodal forces on `nodes` with resultant F acting at p and moment M about p: f_i = F/n + omega x (r_i - mean r), omega from the
    inertia-like tensor of the node cloud, so that sum f = F and sum r x f = M exactly."""
    r = points[nodes] - p
    n = len(nodes)
    cb = r.mean(axis=0)
    d = r - cb
    f = np.tile(F / n, (n, 1))
    J = np.einsum("ij,ij->i", d, d).sum() * np.eye(3) - np.einsum("ij,ik->jk", d, d)
    rhs = M - np.cross(cb, F)
    if np.linalg.matrix_rank(J, tol=1e-6 * max(np.trace(J), 1e-12)) == 3:
        om = np.linalg.solve(J, rhs)
    else:                                   # degenerate cloud (collinear / coplanar): least squares
        om = np.linalg.lstsq(J, rhs, rcond=1e-6)[0]
    return f + np.cross(om, d)


@dataclass
class FEAResult:
    part: str
    case: str
    h: float
    n_tets: int
    n_dof: int
    peak_index: float
    peak_top1: float
    peak_mises_mpa: float
    peak_delam_mpa: float
    peak_where: list
    equilibrium_n: float
    solve_s: float
    max_disp_mm: float
    data: dict = field(default_factory=dict, repr=False)
    info: dict = field(default_factory=dict)

    def summary(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "data"}
        return d


def solve_part(part: PartRec, loads: PartLoads, case: str, h: float, sf: float = 1.0, fine: list | None = None, g_link: np.ndarray | None = None,
               patch_r: float = 2.5, verbose: bool = False, keep_field: bool = True) -> FEAResult:
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve
    from skfem import Basis, BilinearForm, ElementTetP2, ElementVector, LinearForm, MeshTet
    from skfem.helpers import grad

    t0 = time.time()
    mat = get_material(part.material)
    pts, tets = tet_mesh(part, h, fine, verbose=verbose)
    mesh = MeshTet(pts.T.copy(), tets.T.copy())
    basis = Basis(mesh, ElementVector(ElementTetP2()))
    C = stiffness_tensor(mat, part.print_up)

    @BilinearForm
    def stiff(u, v, w):
        eu = 0.5 * (grad(u) + np.swapaxes(grad(u), 0, 1))
        ev = 0.5 * (grad(v) + np.swapaxes(grad(v), 0, 1))
        sig = np.einsum("ijkl,kl...->ij...", C, eu)
        return np.einsum("ij...,ij...->...", sig, ev)

    K = stiff.assemble(basis)
    f = np.zeros(basis.N)
    bnodes = np.unique(mesh.facets[:, mesh.boundary_facets()].ravel())
    # self weight (N): density x fill x g
    fill = float(part.profile.get("fill_fraction", pv(policy(), "print_profile", "mass_fill_fraction")))
    rho = mat.density * 1e-6 * fill
    gv = loads.g_link if g_link is None else g_link

    @LinearForm
    def body(v, w):
        return sum(rho * gv[i] * v.value[i] for i in range(3))

    f += body.assemble(basis)
    node_loaded: list[int] = []
    tot_F, tot_M = np.zeros(3), np.zeros(3)
    for ld in loads.loads:
        nn = select_nodes(pts, bnodes, ld, patch_r)
        fn = distribute(pts, nn, ld.point, ld.F, ld.M)
        for a, ia in enumerate(nn):
            f[basis.nodal_dofs[:, ia]] += fn[a]
        node_loaded += list(nn)
        tot_F += ld.F
    # 3-2-1 supports on three loaded nodes
    ln = np.unique(node_loaded)
    A = ln[0]
    B = ln[np.argmax(np.linalg.norm(pts[ln] - pts[A], axis=1))]
    ab = pts[B] - pts[A]
    area = np.linalg.norm(np.cross(pts[ln] - pts[A], ab), axis=1)
    Cn = ln[int(np.argmax(area))]
    dofs = [basis.nodal_dofs[0, A], basis.nodal_dofs[1, A], basis.nodal_dofs[2, A]]
    ab_u = ab / np.linalg.norm(ab)
    k_ax = int(np.argmax(np.abs(ab_u)))
    other = [i for i in range(3) if i != k_ax]
    dofs += [basis.nodal_dofs[other[0], B], basis.nodal_dofs[other[1], B]] if abs(ab_u[other[0]]) < 0.9 else [basis.nodal_dofs[other[0], B], basis.nodal_dofs[k_ax, B]]
    # third: the component of C normal to the plane ABC
    nrm = np.cross(ab, pts[Cn] - pts[A])
    nrm = nrm / max(np.linalg.norm(nrm), 1e-12)
    kc = int(np.argmax(np.abs(nrm)))
    dofs += [basis.nodal_dofs[kc, Cn]]
    dofs = np.array(sorted(set(int(d) for d in dofs)))
    I = np.setdiff1d(np.arange(basis.N), dofs)
    x = np.zeros(basis.N)
    Kc = K[I][:, I].tocsc()
    x[I] = _linear_solve(Kc, f[I], basis, I)
    # equilibrium: reaction at the supports
    react = (K @ x - f)[dofs]
    eq = float(np.linalg.norm(react))
    comp_ = np.zeros(basis.N, int)
    for r_ in range(3):
        comp_[basis.nodal_dofs[r_]] = r_
        if basis.edge_dofs is not None and basis.edge_dofs.size:
            comp_[basis.edge_dofs[r_]] = r_
    fsum = [float(f[comp_ == r_].sum()) for r_ in range(3)]
    rres = float(np.linalg.norm(Kc @ x[I] - f[I]) / max(np.linalg.norm(f[I]), 1e-12))
    if verbose:
        print("  load sum", np.round(fsum, 3), "rel residual", rres, "reaction", np.round(react, 2))
    # stress at quadrature points
    gu = basis.interpolate(x).grad                 # (3, 3, nel, nqp)
    eps = 0.5 * (gu + np.swapaxes(gu, 0, 1))
    sig = np.einsum("ijkl,kl...->ij...", C, eps)   # (3,3,nel,nqp)
    up = part.print_up / np.linalg.norm(part.print_up)
    sbb = np.einsum("i,ij...,j->...", up, sig, up)
    tr = np.einsum("ij...,j->i...", sig, up)
    tau_b = np.sqrt(np.maximum(np.einsum("i...,i...->...", tr, tr) - sbb ** 2, 0.0))
    # in-plane (layer plane) principal stresses from the 2x2 in-plane block
    e1 = np.cross(up, [1.0, 0, 0] if abs(up[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    s11 = np.einsum("i,ij...,j->...", e1, sig, e1)
    s22 = np.einsum("i,ij...,j->...", e2, sig, e2)
    s12 = np.einsum("i,ij...,j->...", e1, sig, e2)
    mean, rad = 0.5 * (s11 + s22), np.sqrt((0.5 * (s11 - s22)) ** 2 + s12 ** 2)
    s1, s2 = mean + rad, mean - rad
    vm_in = np.sqrt(np.maximum(s1 ** 2 - s1 * s2 + s2 ** 2, 0.0))
    Xa = mat.tensile(90.0)
    Za = mat.tensile(0.0)
    Sz = mat.shear(0.0)
    comp = float(pv(policy(), "knockdown", "compression_over_tensile"))
    idx_d = np.sqrt((np.maximum(sbb, 0.0) / Za) ** 2 + (tau_b / Sz) ** 2)
    idx_p = np.maximum.reduce([np.maximum(s1, 0.0) / Xa, vm_in / Xa, np.maximum(-s2, 0.0) / (Xa * comp)])
    FI = np.maximum(idx_d, idx_p)
    el_max = FI.max(axis=1)
    k = max(1, int(0.01 * len(el_max)))
    top1 = float(np.sort(el_max)[-k:].mean())
    ie, iq = np.unravel_index(int(np.argmax(FI)), FI.shape)
    qp = basis.global_coordinates()                 # DiscreteField (3, nel, nqp)
    where = [float(qp.value[0, ie, iq]), float(qp.value[1, ie, iq]), float(qp.value[2, ie, iq])]
    # von Mises of the full tensor
    tr3 = np.einsum("ii...->...", sig)
    vm = np.sqrt(np.maximum(1.5 * (np.einsum("ij...,ij...->...", sig, sig) - tr3 ** 2 / 3.0) * 1.0 + 0.0, 0.0))
    disp = x[basis.nodal_dofs]
    res = FEAResult(part.id, case, h, int(mesh.t.shape[1]), int(basis.N), float(FI.max()), top1, float(vm.max()), float(np.maximum(sbb, 0).max()), where, eq,
                    time.time() - t0, float(np.linalg.norm(disp, axis=0).max()))
    res.info = {"fe_load_sum_n": tot_F.tolist(), "sf": sf}
    if keep_field:
        res.data = {"mesh": mesh, "basis": basis, "x": x, "FI": FI, "sig": sig, "sbb": sbb, "qp_xyz": qp.value, "el_max": el_max}
    return res


def converge(part: PartRec, loads: PartLoads, case: str, h0: float, ratio: float = 1.6, fine: list | None = None, verbose: bool = False) -> dict:
    """Two mesh densities (h0 and h0/ratio, refinement balls scaled the same way). Reports the change of the peak failure index."""
    r1 = solve_part(part, loads, case, h0, fine=fine, verbose=verbose, keep_field=False)
    fine2 = [(c, rad, sz / ratio) for c, rad, sz in (fine or [])]
    r2 = solve_part(part, loads, case, h0 / ratio, fine=fine2, verbose=verbose, keep_field=True)
    d_peak = abs(r2.peak_index - r1.peak_index) / max(r2.peak_index, 1e-12)
    d_top = abs(r2.peak_top1 - r1.peak_top1) / max(r2.peak_top1, 1e-12)
    d_disp = abs(r2.max_disp_mm - r1.max_disp_mm) / max(r2.max_disp_mm, 1e-12)
    return {"coarse": r1.summary(), "fine": r2.summary(), "peak_change": d_peak, "top1_change": d_top, "disp_change": d_disp,
            "converged_10pct": bool(d_top <= 0.10), "result": r2}
