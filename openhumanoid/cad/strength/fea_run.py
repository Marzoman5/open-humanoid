"""FEA driver: the worst gated analytic case of a part, meshed at two densities, with the convergence and the analytic cross-check.

For each part: take the analytic row with the smallest gated margin of check 'section' (its scenario and the fibre location of the peak
stress), rebuild that scenario's loads on the part, refine the mesh around the analytic hot spot and every internal corner, solve at h and
h/ratio, and report
  * failure-index peak / mean of the worst 1% of elements at both densities (convergence within 10% of the finer one is the acceptance test),
  * the FEA margin  1 / (SF x peak index)   (the index already is stress / weakest-direction allowable),
  * the nominal normal stress at the analytic section against the beam-theory value (sanity check of the analytic engine).
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np

from . import fea, loadcases, loadpath
from .analytic import sf_of
from .loadpath import Topology
from .model import Model


def _pick_row(res: dict, part: str) -> dict | None:
    rows = [r for r in res["rows"] if r["part"] == part and r["gate"] and r["check"] == "section"]
    return min(rows, key=lambda r: r["margin"]) if rows else None


def mesh_size_for(volume_mm3: float, target_tets: int = 7000) -> float:
    return float((volume_mm3 / (0.118 * target_tets)) ** (1.0 / 3.0))


def run_fea(model: Model, cfg: dict, res: dict, parts: list[str], out: Path | None = None, ratio: float = 1.6, target_tets: int = 7000,
            verbose: bool = True) -> dict:
    excl = cfg.get("exclude_parts", [])
    topo = Topology(model, excl)
    mo = loadcases.actuator_masses(model, cfg)
    out_all: dict = {}
    for pid in parts:
        t0 = time.time()
        part = model.parts[pid]
        row = _pick_row(res, pid)
        if row is None:
            continue
        scs, _ = loadcases.build(model, cfg, [row["case"]])
        sc = [s for s in scs if s.name == row["case"]][0]
        loads, diag = loadpath.solve(model, topo, sc, mo)
        pl = loads[pid]
        fib = np.asarray(row["info"]["fibre_xyz"])
        h = mesh_size_for(part.volume, target_tets)
        balls = [(fib, max(6.0, 2.0 * h), h / 3.0)]
        for c in part.corners:
            if c["length"] >= 3.0:
                balls.append((np.asarray(c["mid"]), 5.0, h / 3.0))
        balls = balls[:12]
        sf, _f, _g = sf_of(row["cls"])
        if verbose:
            print(f"FEA {pid}: case {row['case']} (margin {row['margin']:.3f}), h={h:.1f} mm, {len(balls)} refinement zones", flush=True)
        cv = fea.converge(part, pl, row["case"], h, ratio, balls, probe=(fib, 3.0))
        fine: fea.FEAResult = cv.pop("result")
        # nominal comparison at the analytic section
        n = np.asarray(row["info"]["normal"])
        d = fine.data
        xyz = d["qp_xyz"]                                     # (3, nel, nqp)
        X = np.moveaxis(xyz, 0, -1).reshape(-1, 3)
        sig = d["sig"]                                        # (3, 3, nel, nqp)
        snn = np.einsum("i,ij...,j->...", n, sig, n).reshape(-1)
        sel = (np.linalg.norm(X - fib, axis=1) < 2.5) & (np.abs((X - fib) @ n) < 1.0)
        fe_nom = float(snn[sel].max()) if sel.any() else float("nan")
        an_nom = float(row["info"]["sigma_mpa"])
        # corner-free comparison: far-field value two thicknesses along the load path is not available generally; report both with Kt
        cv.update({"part": pid, "case": row["case"], "class": row["cls"], "sf": sf, "analytic_margin": row["margin"],
                   "fea_margin": 1.0 / (sf * fine.peak_index) if fine.peak_index > 0 else 1e9,
                   "fea_margin_top1": 1.0 / (sf * fine.peak_top1) if fine.peak_top1 > 0 else 1e9,
                   "fea_margin_away": 1.0 / (sf * fine.peak_away) if fine.peak_away > 0 else 1e9,
                   "fea_margin_top1_away": 1.0 / (sf * fine.top1_away) if fine.top1_away > 0 else 1e9,
                   "analytic_sigma_mpa": an_nom, "analytic_kt": row["info"].get("kt"), "fea_sigma_nn_at_fibre_mpa": fe_nom,
                   "fea_over_analytic_nominal": fe_nom / an_nom if an_nom > 0 else float("nan"), "wall_s": time.time() - t0})
        out_all[pid] = cv
        if out is not None:
            try:
                from .fea_plot import plot_fea

                plot_fea(part, fine, out / f"fea_{pid}.png", f"{pid} - {row['case']}")
            except Exception as exc:  # noqa: BLE001
                cv["plot_error"] = str(exc)
        if verbose:
            c, f_ = cv["coarse"], cv["fine"]
            print(f"  coarse: {c['n_tets']} tets peak {c['peak_index']:.2f} away {c['peak_away']:.2f} top1-away {c['top1_away']:.2f} probe {c['probe_mean']:.2f} | fine: {f_['n_tets']} tets peak {f_['peak_index']:.2f} "
                  f"away {f_['peak_away']:.2f} top1-away {f_['top1_away']:.2f} probe {f_['probe_mean']:.2f} | change: peak-away {cv['peak_away_change'] * 100:.1f}% top1-away {cv['top1_away_change'] * 100:.1f}% probe {cv['probe_change'] * 100:.1f}% | "
                  f"FEA margin(away) {cv['fea_margin_away']:.3f} vs analytic {row['margin']:.3f} | sigma_nn FE {fe_nom:.1f} vs analytic {an_nom:.1f} MPa", flush=True)
    return out_all
