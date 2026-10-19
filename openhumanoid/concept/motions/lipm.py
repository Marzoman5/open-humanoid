"""Linear inverted pendulum + ZMP preview control (own implementation of the classical method).

Reference: S. Kajita, F. Kanehiro, K. Kaneko, K. Fujiwara, K. Harada, K. Yokoi, H. Hirukawa, "Biped walking pattern
generation by using preview control of zero-moment point", IEEE ICRA 2003 (DOI 10.1109/ROBOT.2003.1241826).
Written from the paper's equations. Open Duck's generator has no licence and was not read or used.
"""
from __future__ import annotations

import numpy as np

G = 9.81


def _dare(A, B, Q, R, iters: int = 20000, tol: float = 1e-12):
    P = Q.copy()
    for _ in range(iters):
        BtP = B.T @ P
        K = np.linalg.solve(R + BtP @ B, BtP @ A)
        Pn = Q + A.T @ P @ (A - B @ K)
        if np.abs(Pn - P).max() < tol:
            return Pn
        P = Pn
    return P


class PreviewController:
    """Preview controller for p = c - (zc/g) * c_ddot with jerk input, sampling dt, preview horizon `horizon_s`."""

    def __init__(self, zc: float, dt: float, horizon_s: float = 1.6, qe: float = 1.0, r: float = 1e-6):
        self.dt, self.N = dt, int(round(horizon_s / dt))
        A = np.array([[1, dt, dt * dt / 2], [0, 1, dt], [0, 0, 1.0]])
        B = np.array([[dt ** 3 / 6], [dt * dt / 2], [dt]])
        C = np.array([[1.0, 0.0, -zc / G]])
        self.A, self.B, self.C = A, B, C
        At = np.zeros((4, 4))
        At[0, 0] = 1.0
        At[0, 1:] = (C @ A)[0]
        At[1:, 1:] = A
        Bt = np.vstack([C @ B, B])
        It = np.array([[1.0], [0], [0], [0]])
        Q = np.diag([qe, 0, 0, 0])
        R = np.array([[r]])
        P = _dare(At, Bt, Q, R)
        Ra = np.linalg.inv(R + Bt.T @ P @ Bt)
        K = Ra @ Bt.T @ P @ At
        self.Ks, self.Kx = float(K[0, 0]), K[0, 1:]
        Ac = At - Bt @ K
        X = -Ac.T @ P @ It
        Gd = np.zeros(self.N)
        Gd[0] = -self.Ks
        for i in range(1, self.N):
            Gd[i] = float((Ra @ Bt.T @ X)[0, 0])
            X = Ac.T @ X
        self.Gd = Gd

    def run(self, zmp_ref: np.ndarray, x0=(0.0, 0.0, 0.0)):
        """zmp_ref (T,) -> (com (T,), zmp (T,)). Pads the end of the reference so the preview window is full."""
        T = len(zmp_ref)
        pad = np.concatenate([zmp_ref, np.full(self.N, zmp_ref[-1])])
        x = np.array(x0, float).reshape(3, 1)
        com, zmp = np.zeros(T), np.zeros(T)
        esum = 0.0
        for k in range(T):
            p = float((self.C @ x)[0, 0])
            com[k], zmp[k] = x[0, 0], p
            esum += p - zmp_ref[k]
            u = -self.Ks * esum - float(self.Kx @ x[:, 0]) - float(self.Gd @ pad[k + 1:k + 1 + self.N])
            x = self.A @ x + self.B * u
        return com, zmp
