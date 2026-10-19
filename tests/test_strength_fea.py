"""FEA (scikit-fem on a gmsh tetrahedral mesh) against beam theory on a cantilever bar, and mesh convergence."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

bd = pytest.importorskip("build123d")
pytest.importorskip("gmsh")
pytest.importorskip("skfem")

from openhumanoid.cad.core import box_at, mesh_of  # noqa: E402
from openhumanoid.cad.strength import fea  # noqa: E402
from openhumanoid.cad.strength.loadpath import Load, PartLoads  # noqa: E402
from openhumanoid.cad.strength.model import PartRec  # noqa: E402

L, B, H, F = 80.0, 10.0, 10.0, 20.0


def bar_part() -> PartRec:
    shape = box_at(bd.Location(), (L, B, H), (L / 2, 0, 0))
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "p.step")
        bd.export_step(shape, fp)
        step = open(fp, "rb").read()
    m = mesh_of(shape)
    return PartRec("bar", "link", "frame", "fdm", "petg", None, 0.0, np.array([0, 0, 1.0]), m, float(m.volume), np.array(m.center_mass), [], {}, {}, [], step)


def bar_loads() -> PartLoads:
    pl = PartLoads("bar", "link", g_link=np.zeros(3))
    big = {"type": "sphere", "r": 4.0}
    pl.loads = [Load(np.array([L, 0, 0.0]), np.array([0, 0, F]), np.zeros(3), "tip", big),
                Load(np.array([0.0, 0, 0.0]), np.array([0, 0, -F]), np.array([0, F * L, 0.0]), "root", big)]
    return pl


def test_cantilever_fea_matches_beam_theory_and_converges():
    part, pl = bar_part(), bar_loads()
    r1 = fea.solve_part(part, pl, "tip", h=4.0, keep_field=True)
    r2 = fea.solve_part(part, pl, "tip", h=2.8, keep_field=True)
    I = B * H ** 3 / 12.0
    sig_beam = F * (L / 2) * (H / 2) / I

    def midspan(res):
        X = np.moveaxis(res.data["qp_xyz"], 0, -1).reshape(-1, 3)
        sxx = res.data["sig"][0, 0].reshape(-1)
        sel = (np.abs(X[:, 0] - L / 2) < 3.0) & (X[:, 2] > 0.6 * H / 2)
        return float(abs(sxx[sel].mean()))

    assert abs(res_eq := r2.equilibrium_n) < 1e-3                       # the supports carry nothing: the applied loads are self-equilibrated
    assert midspan(r2) == pytest.approx(0.8 * sig_beam, rel=0.10)      # mean over the outer fifth (z = 3..5 mm) at mid-span: sigma(z = 4 mm)
    assert abs(midspan(r1) - midspan(r2)) / midspan(r2) < 0.10          # two mesh densities agree within 10%
    assert r2.n_tets > 2 * r1.n_tets


def test_fea_distribution_is_equilibrated_for_force_and_moment():
    pts = np.random.default_rng(1).normal(size=(30, 3)) * 3 + np.array([5.0, 2.0, 1.0])
    p = np.array([5.0, 2.0, 1.0])
    Fv, Mv = np.array([3.0, -2.0, 11.0]), np.array([100.0, -40.0, 25.0])
    f = fea.distribute(pts, np.arange(30), p, Fv, Mv)
    assert np.allclose(f.sum(axis=0), Fv)
    assert np.allclose(np.cross(pts - p, f).sum(axis=0), Mv)
