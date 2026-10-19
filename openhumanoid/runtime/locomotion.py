"""Online footstep planner: hold / weight shift / step, with divergent-component-of-motion (DCM) foot placement from the MEASURED state.

This is the walking and push-recovery brain. It runs every control tick:

* a *virtual* LIPM (COM position and velocity in the planner's world frame) is advanced with the planned centre of pressure (COP)
  and pulled toward the state measured by the estimator (so a push or a slip enters the plan);
* the swing foot lands where the predicted DCM needs it (deadbeat landing rule, exact for the planned COP ramp over the double-support
  phase), so the same code steps forward, back, sideways, turns, stops, and takes a capture step after a push;
* the pelvis target is the virtual COM minus the kinematic COM offset (2 FK passes), the legs follow by analytic IK.

Nominal orbit. With step time T, double-support T_ds, omega = sqrt(g / z_com), kappa = (e^{w T_ds} - 1 - w T_ds) / (w T_ds):
the DCM offset to the new stance foot at step start is b = (1 + kappa) * L / (e^{wT} - 1) along the motion and
(1 + kappa) * s_y * w0 / (e^{wT} + 1) across it (alternating), and the landing displacement that reaches it from the current offset u is
dP = (e^{w (t_rem + T_ds)} u - b_next) / (1 + kappa). Written from the equations; see docs/software.md for the derivation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..concept.kin import lower_body, quat_from_yaw_pitch, smoothstep5
from .estimator import EstState
from .model import G, RobotModel


def R2(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


@dataclass
class GaitConfig:
    step_time: float = 0.36
    ds_frac: float = 0.22
    clearance: float = 0.014
    lift_frac: float = 0.8            # swing foot reaches its landing point this fraction of the way through the swing time
    flex: float | None = None         # stance knee flexion [rad]; None: the concept's own
    w_foot: float | None = None       # nominal foot spacing (ankle to ankle); None: hip spacing
    shift_time_max: float = 0.9
    capture_step_time: float = 0.26    # faster step for reactive (capture) steps
    step_cop_gain: float = 2.5
    shift_gain: float = 2.5
    shift_gain_capture: float = 2.0
    freeze_s: float = 0.045           # stop re-targeting the landing this long before touchdown
    bias_tau: float = 0.6
    lead_s: float = 0.03              # the pelvis command leads the planned COM by this (cancels the servo/leg lag so the real COM follows the plan)
    track_lag_s: float = 0.02        # lag between the commanded COM and the measured one (servo + compliance + estimator)
    touchdown_reseed: float = 0.3
    kp_c: float = 0.0                 # COM position/velocity error (measured vs commanded, lag-aligned) fed back into the pelvis command
    kd_c: float = 0.0
    meas_gain: float = 0.0            # how much of the measured DCM error enters the foot placement
    blend_c: float = 0.0             # per-tick pull of the virtual COM position toward the measurement
    blend_v: float = 0.0
    hold_k_shift: float = 1.5
    hold_k: float = 2.5               # DCM gain in hold (COP = xi + k (xi - xi_ref))
    cop_margin: float = 0.75          # COP kept inside this fraction of the foot rectangle
    vmax: tuple = (0.16, 0.08, 0.6)   # |vx|, |vy|, |wz|
    max_step: tuple = (0.07, 0.05)    # longest step (forward, sideways increment) [m]
    gap_min: float = 0.016            # min clear gap between the feet (lateral) [m]
    capture_x: float = 0.030          # in hold: step when the measured DCM is this far from the support centre (forward/back) [m]
    capture_y: float = 0.045          # (sideways)
    capture_enable: bool = True
    arm_swing: float = 1.0


@dataclass
class LowerTarget:
    pelvis: np.ndarray               # world xyz (planner frame)
    yaw: float
    pitch: float
    ankle: dict                      # side -> world xyz of the ankle origin
    foot_yaw: dict
    contact: np.ndarray              # [l, r]
    mode: str
    info: dict = field(default_factory=dict)


class Gait:
    def __init__(self, model: RobotModel, cfg: GaitConfig | None = None):
        self.m = model
        self.cfg = cfg or GaitConfig()
        lg = model.lg
        self.lg = lg
        self.flex = self.cfg.flex if self.cfg.flex is not None else model.walk_flex
        self.w0 = self.cfg.w_foot if self.cfg.w_foot is not None else 2 * lg.hip_y
        # geometry of the stand pose
        from ..concept.motions.common import stand_geometry
        sg = stand_geometry(model.kin, self.flex)
        self.pelvis_z = sg["pelvis_z"]
        self.zc = self._com_height()
        self.omega = math.sqrt(G / self.zc)
        self.reset()

    # ------------------------------------------------------------------ setup
    def _com_height(self) -> float:
        from ..concept.motions.common import stand_geometry
        k = self.m.kin
        q = self.m.stand_q(self.flex)
        pel = np.array([0, 0, self.pelvis_z])
        c = k.com(q, pel, quat_from_yaw_pitch(0.0, 0.0)[0])
        self.com_off0 = c[:2] - pel[:2]
        return float(c[2] - self.lg.ankle_h)

    def reset(self, feet: dict | None = None, com_world: np.ndarray | None = None) -> None:
        lg = self.lg
        self.feet = feet or {"l": np.array([0.0, lg.hip_y, 0.0]), "r": np.array([0.0, -lg.hip_y, 0.0])}   # ankle x, y, yaw (planner world)
        mid = self._support_centre({"l": 0.5, "r": 0.5})
        self.v_c = mid.copy() if com_world is None else np.asarray(com_world, float).copy()
        self.v_v = np.zeros(2)
        self.mode = "hold"
        self.t_mode = 0.0
        self.stance = "l"
        self.cmd = np.zeros(3)
        self.step_index = 0
        self.sw_pos = np.zeros(3)
        self.sw_start = np.zeros(3)
        self.sw_target = np.zeros(3)
        self.sw_prog = 0.0
        self.sw_height = 0.0
        self.cop = mid.copy()
        self.contact = np.array([0.5, 0.5])
        self.stop_pending = False
        self.shift_cop = mid.copy()
        self.com_off = self.com_off0.copy()
        self.pelvis_yaw = 0.0
        self.landed_yaw = 0.0
        self.last_info: dict = {}
        self.n_steps_taken = 0
        self.ramp_from = "l"
        self.step_cmd = np.zeros(3)
        self.hold_target = None
        self.bias = np.zeros(2)
        self.hist = []
        self.err_c = np.zeros(2)
        self.err_v = np.zeros(2)
        self.dcm_err = np.zeros(2)
        self.capture_mode = False
        self.meas_c = np.zeros(2)
        self.meas_v = np.zeros(2)

    # ------------------------------------------------------------------ geometry helpers
    def centre_of(self, side: str) -> np.ndarray:
        f = self.feet[side]
        return f[:2] + self.lg.foot_off * np.array([math.cos(f[2]), math.sin(f[2])])

    def _support_centre(self, w: dict) -> np.ndarray:
        return w.get("l", 0) * self.centre_of("l") + w.get("r", 0) * self.centre_of("r") if hasattr(self, "feet") else np.zeros(2)

    def _cop_limit(self, p: np.ndarray, sides: list) -> np.ndarray:
        """Clip a COP to the union hull approx: the rectangle(s) of the listed feet (shrunk), enlarged to their convex hull in the heading frame."""
        lg = self.lg
        hx, hy = 0.5 * lg.foot_len * self.cfg.cop_margin, 0.5 * lg.foot_w * self.cfg.cop_margin
        psi = self.pelvis_yaw
        Rm = R2(psi)
        pts = []
        for sd in sides:
            c = self.centre_of(sd)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts.append(c + Rm @ np.array([sx * hx, sy * hy]))
        P = np.array(pts)
        loc = Rm.T @ (p - P.mean(0))
        lo = (Rm.T @ (P - P.mean(0)).T).T
        mn, mx = lo.min(0), lo.max(0)
        loc = np.clip(loc, mn, mx)
        return P.mean(0) + Rm @ loc

    # ------------------------------------------------------------------ commands
    def command(self, vx: float, vy: float, wz: float) -> None:
        vm = self.cfg.vmax
        self.cmd = np.array([np.clip(vx, -vm[0], vm[0]), np.clip(vy, -vm[1], vm[1]), np.clip(wz, -vm[2], vm[2])])

    @property
    def walking(self) -> bool:
        return self.mode in ("shift", "step")

    # ------------------------------------------------------------------ estimator interface
    def _measured_com(self, est: EstState) -> tuple:
        """Measured COM and velocity in the planner world frame."""
        Rm = R2(self.pelvis_yaw)
        if self.mode in ("step",):
            sd = self.stance
            if self.t_mode > self.t_ss():
                # double support after landing: roles are mixed -> support weighted
                base = self._support_centre({"l": self.contact[0], "r": self.contact[1]})
                c = est.c[:2]
                v = est.v[:2]
            else:
                base = self.centre_of(sd)
                c = est.c_foot[sd][:2]
                v = est.v_foot[sd][:2]
        else:
            base = self._support_centre({"l": self.contact[0], "r": self.contact[1]})
            c, v = est.c[:2], est.v[:2]
        return base + Rm @ c, Rm @ v

    @property
    def T_cur(self) -> float:
        return self.cfg.capture_step_time if getattr(self, "capture_mode", False) else self.cfg.step_time

    def t_ss(self) -> float:
        return self.T_cur * (1 - self.cfg.ds_frac)

    def t_ds(self) -> float:
        return self.T_cur * self.cfg.ds_frac

    def contact_hint(self) -> np.ndarray:
        return self.contact.copy()

    # ------------------------------------------------------------------ core update
    def update(self, est: EstState, dt: float, allow_capture: bool = True) -> LowerTarget:
        cfg = self.cfg
        w = self.omega
        c_meas, v_meas = self._measured_com(est)
        # slow plant-error estimate: where the real COM sits relative to what was commanded (servo sag, compliance). It is compensated in the
        # pelvis command and removed from the state used for control, so sag does not read as a disturbance.
        # the virtual (commanded) COM, delayed by the measured tracking lag, is what the measurement should equal; the difference is the disturbance
        lag_n = max(int(round(cfg.track_lag_s / dt)), 0)
        self.hist.append((self.v_c.copy(), self.v_v.copy()))
        if len(self.hist) > lag_n + 1:
            del self.hist[0]
        c_lag, v_lag = self.hist[0]
        a_b = dt / cfg.bias_tau
        self.bias = np.clip(self.bias + a_b * ((c_meas - c_lag) - self.bias), -0.04, 0.04)
        dcm_meas = (c_meas - self.bias) + v_meas / w
        dcm_lagged = c_lag + v_lag / w
        dcm_virt = self.v_c + self.v_v / w
        err = dcm_meas - dcm_lagged                        # disturbance seen by the sensors
        dcm = dcm_virt + cfg.meas_gain * err
        self.dcm_meas = dcm_meas
        self.dcm_err = err
        self.err_c, self.err_v = (c_meas - self.bias) - c_lag, v_meas - v_lag
        self.meas_c, self.meas_v = c_meas - self.bias, v_meas.copy()
        self.t_mode += dt
        info = {"dcm": dcm.copy(), "mode": self.mode}

        if self.mode == "hold":
            self._hold(dcm, dt, est, info, allow_capture)
        elif self.mode == "shift":
            self._shift(dcm, dt, info)
        else:
            self._step(dcm, dt, info)
        # advance the virtual LIPM with the planned COP
        self._lipm(self.cop, dt)
        self.last_info = info
        return self._lower_target(est, info)

    def _lipm(self, p: np.ndarray, dt: float) -> None:
        w = self.omega
        ch, sh = math.cosh(w * dt), math.sinh(w * dt)
        x, v = self.v_c - p, self.v_v
        self.v_c = p + x * ch + v / w * sh
        self.v_v = w * x * sh + v * ch

    # ---------------- hold
    def _hold(self, dcm, dt, est, info, allow_capture):
        cfg = self.cfg
        both = [s for s in "lr"]
        ref = self._support_centre({"l": 0.5, "r": 0.5})
        if self.hold_target is not None:
            ref = ref + self.hold_target
        # the commanded COM glides to the reference (first-order, 0.15 s); the posture is stiff, the push is absorbed by the servos and the
        # stabiliser, and the DCM monitor below decides when that is not enough
        a = 1 - math.exp(-dt / 0.15)
        self.v_c = self.v_c + a * (ref - self.v_c)
        self.v_v = np.zeros(2)
        self.cop = self.v_c.copy()
        self.contact = np.array([0.5, 0.5])
        Rm = R2(self.pelvis_yaw)
        out = Rm.T @ (self.dcm_meas - ref)
        hull_x = 0.5 * self.lg.foot_len * 0.5
        hull_y = self.lg.hip_y + 0.5 * self.lg.foot_w * 0.5
        info["dcm_out"] = float(max(abs(out[0]) - hull_x, abs(out[1]) - hull_y))
        info["dcm_rel"] = out.copy()
        walk_cmd = np.linalg.norm(self.cmd[:2]) > 1e-3 or abs(self.cmd[2]) > 1e-3
        if walk_cmd:
            self._start_walk(self.v_c + 0 * dcm)
        elif allow_capture and cfg.capture_enable and (abs(out[0]) > cfg.capture_x or abs(out[1]) > cfg.capture_y):
            self._start_walk(self.dcm_meas, capture=True)

    def _start_walk(self, dcm, capture: bool = False):
        # stance foot: the side the DCM is on laterally (the foot toward which the weight must go); for ties the left
        Rm = R2(self.pelvis_yaw)
        mid = self._support_centre({"l": 0.5, "r": 0.5})
        out = Rm.T @ (dcm - mid)
        if capture:
            # swing the foot that lies on the side of the push (forward/back pushes: the foot that is not loaded more); keep stance = opposite lateral side of the DCM
            self.stance = "r" if out[1] < 0 else "l"
        else:
            # first stance: opposite the first swing; walk-in-place starts with the right foot stepping
            self.stance = "l"
            vy = self.cmd[1]
            if vy < -1e-3:
                self.stance = "l"
            elif vy > 1e-3:
                self.stance = "r"
        self.mode = "shift"
        self.t_mode = 0.0
        self.capture_mode = capture
        self.shift_started = dcm.copy()
        if capture:
            self.v_c = self.v_c + self.err_c
            self.v_v = self.v_v + self.err_v

    # ---------------- weight shift
    def _shift(self, dcm, dt, info):
        cfg = self.cfg
        sd = self.stance
        p_s = self.centre_of(sd)
        other = "r" if sd == "l" else "l"
        w = self.omega
        Rm = R2(self.pelvis_yaw)
        # target DCM: the periodic offset b over the stance foot (lateral part only; the forward part comes from the first step)
        T = self.T_cur
        s_y = -1.0 if sd == "l" else 1.0           # the NEXT stance (swing foot) side relative to this stance foot: left stance -> next on the right
        b_lat = (1 + self._kappa()) * s_y * self.w0 / (math.exp(w * T) + 1)
        target = p_s + Rm @ np.array([0.0, b_lat])
        u = Rm.T @ (dcm - p_s)
        u_t = Rm.T @ (target - p_s)
        tleft = max(cfg.shift_time_max - self.t_mode, 0.05)
        err = u[1] - u_t[1]
        # constant COP that brings the lateral DCM to the target after 0.28 s (clamped to the double-support hull)
        # DCM tracking: COP = xi_t + (1 + K)(xi - xi_t) makes the DCM error decay with rate K * omega (monotonic, no overshoot). The target
        # is the periodic offset over the stance foot laterally and, forward, the stance centre line (a capture step wants the DCM slowed).
        K = cfg.shift_gain_capture if self.capture_mode else cfg.shift_gain
        u_ref = np.array([0.0, u_t[1]])
        p_loc = u_ref + (1 + K) * (u - u_ref)
        p = p_s + Rm @ p_loc
        self.cop = self._cop_limit(p, ["l", "r"])
        self.contact = np.array([0.5, 0.5])
        info["shift_err"] = float(err)
        done = abs(err) < 0.0015 or self.t_mode > cfg.shift_time_max
        if done and self.t_mode > 0.06:
            self._begin_step(dcm)

    def _kappa(self) -> float:
        w, tds = self.omega, self.t_ds()
        return (math.exp(w * tds) - 1 - w * tds) / (w * tds)

    # ---------------- step
    def _begin_step(self, dcm):
        self.mode = "step"
        self.t_mode = 0.0
        sd = self.stance
        sw = "r" if sd == "l" else "l"
        self.sw_start = self.feet[sw].copy()
        self.sw_pos = self.feet[sw].copy()
        self.sw_target = self.feet[sw].copy()
        self.sw_prog = 0.0
        self.step_cmd = self.cmd.copy()
        self.stop_step = bool(np.linalg.norm(self.cmd[:2]) < 1e-3 and abs(self.cmd[2]) < 1e-3)

    def _step(self, dcm, dt, info):
        cfg = self.cfg
        w = self.omega
        sd = self.stance
        sw = "r" if sd == "l" else "l"
        T, Tss, Tds = self.T_cur, self.t_ss(), self.t_ds()
        t = self.t_mode
        p_s = self.centre_of(sd)
        kap = self._kappa()
        cmd = self.cmd if not self.stop_step else np.zeros(3)
        if self.stop_step is False and np.linalg.norm(self.cmd[:2]) < 1e-3 and abs(self.cmd[2]) < 1e-3:
            self.stop_step = True                    # stop requested mid-swing: land square
            cmd = np.zeros(3)
        if t <= Tss:
            # ---- single support: stance fixed; COP over the stance foot centre, modulated inside the foot to hold the DCM on the nominal orbit
            xi_ref = self._xi_ref(sd, cmd, t)
            e = dcm - xi_ref
            p = p_s + cfg.step_cop_gain * e
            self.cop = self._cop_limit(p, [sd])
            info["xi_err"] = e.copy()
            self.contact = np.array([1.0, 0.0]) if sd == "l" else np.array([0.0, 1.0])
            if t < Tss - cfg.freeze_s or self.sw_prog < 1e-9:
                self.sw_target = self._landing(sd, cmd, dcm, Tss - t)
            # advance the swing foot along the re-targeted minimum-jerk profile, reaching the landing at lift_frac * Tss
            Tsw = cfg.lift_frac * Tss
            s_now = float(smoothstep5(t / Tsw))
            s_prev = float(smoothstep5(max(t - dt, 0.0) / Tsw))
            if s_prev < 1 - 1e-9:
                f = (s_now - s_prev) / (1 - s_prev)
                self.sw_pos = self.sw_pos + (self.sw_target - self.sw_pos) * f
            else:
                self.sw_pos = self.sw_target.copy()
            self.sw_prog = s_now
            self.sw_height = cfg.clearance * 0.5 * (1 - math.cos(2 * math.pi * min(t / Tss, 1.0)))
            info["landing"] = self.sw_target[:2].copy()
            info["phase"] = "ss"
        else:
            # ---- double support: COP ramps from the old stance foot to the landing foot
            if t - dt <= Tss:                          # touchdown
                self.feet[sw] = self.sw_pos.copy()
                self.sw_height = 0.0
                self.v_c = self.v_c + cfg.touchdown_reseed * self.err_c
                self.v_v = self.v_v + cfg.touchdown_reseed * self.err_v
            s = (t - Tss) / Tds
            p_n = self.centre_of(sw)
            self.cop = p_s + (p_n - p_s) * float(np.clip(s, 0, 1))
            sp = float(np.clip(s, 0, 1))
            self.contact = (np.array([1 - sp, sp]) if sd == "l" else np.array([sp, 1 - sp]))
            info["phase"] = "ds"
            if t >= T:
                self._end_step(dcm)

    def _xi_ref(self, sd: str, cmd: np.ndarray, t: float) -> np.ndarray:
        """Nominal DCM at time t of a single-support phase (world frame): the periodic orbit, or the square-stop approach."""
        w, T, kap = self.omega, self.T_cur, self._kappa()
        sw = "r" if sd == "l" else "l"
        f_s = self.feet[sd]
        Rs = R2(f_s[2])
        p_s = self.centre_of(sd)
        s_y = 1.0 if sw == "l" else -1.0
        if self.stop_step:
            d_nom = np.array([0.0, s_y * self.w0])
            return p_s + Rs @ (0.5 * d_nom * math.exp(w * (t - self.t_ss())))
        e1 = math.exp(w * T)
        Lx, Ly = cmd[0] * T, cmd[1] * T
        b_S = (1 + kap) * np.array([Lx / (e1 - 1), Ly / (e1 - 1) + s_y * self.w0 / (e1 + 1)])
        return p_s + Rs @ (b_S * math.exp(w * t))

    def _landing(self, sd: str, cmd: np.ndarray, dcm: np.ndarray, t_rem_ss: float) -> np.ndarray:
        cfg, w, T = self.cfg, self.omega, self.T_cur
        kap = self._kappa()
        sw = "r" if sd == "l" else "l"
        f_s = self.feet[sd]
        psi_s = f_s[2]
        p_s = self.centre_of(sd)
        s_y = 1.0 if sw == "l" else -1.0                     # side of the swing foot relative to the stance foot
        dpsi = float(cmd[2] * T)
        if self.stop_step:
            dpsi = 0.0
        if self.stop_step:
            d_nom = np.array([0.0, s_y * self.w0])
            b_N = -0.5 * d_nom                                 # land square: the DCM ends midway between the feet
        else:
            Lx, Ly = cmd[0] * T, cmd[1] * T
            d_nom = np.array([Lx, s_y * self.w0 + Ly])
            e1 = math.exp(w * T)
            b_N = (1 + kap) * np.array([Lx / (e1 - 1) , Ly / (e1 - 1) - s_y * self.w0 / (e1 + 1)])
        # express in the stance-foot frame
        Rs = R2(psi_s)
        b_S = Rs @ (R2(dpsi) @ b_N) if not self.stop_step else Rs @ b_N
        u = dcm - p_s
        dP = (math.exp(w * (t_rem_ss + self.t_ds())) * u - b_S) / (1 + kap)
        # dP is a displacement of the new stance CENTRE; convert to the ankle position of the landing foot
        centre_new = p_s + dP
        psi_n = psi_s + dpsi
        ankle_new = centre_new - self.lg.foot_off * np.array([math.cos(psi_n), math.sin(psi_n)])
        # kinematic limits in the stance frame
        loc = Rs.T @ (ankle_new - f_s[:2])
        mx, my = cfg.max_step
        loc[0] = np.clip(loc[0], -mx * 1.0, mx)
        # lateral: keep at least gap_min clear and no further than reach
        gap_min = self.lg.foot_w + cfg.gap_min
        side = 1.0 if sw == "l" else -1.0
        lat = loc[1] * side
        lat = np.clip(lat, gap_min, 2 * self.lg.hip_y + 2 * my)
        loc[1] = lat * side
        ankle_new = f_s[:2] + Rs @ loc
        return np.array([ankle_new[0], ankle_new[1], psi_n])

    def _end_step(self, dcm):
        sd = self.stance
        sw = "r" if sd == "l" else "l"
        self.stance = sw
        self.step_index += 1
        self.n_steps_taken += 1
        self.t_mode = 0.0
        stop_now = self.stop_step
        walk_cmd = np.linalg.norm(self.cmd[:2]) > 1e-3 or abs(self.cmd[2]) > 1e-3
        if stop_now and not walk_cmd:
            self.capture_mode = False
            self.mode = "hold"
            self.contact = np.array([0.5, 0.5])
            return
        self.sw_start = self.feet[sd].copy()
        self.sw_pos = self.feet[sd].copy()
        self.sw_target = self.feet[sd].copy()
        self.sw_prog = 0.0
        self.step_cmd = self.cmd.copy()
        self.stop_step = not walk_cmd
        self.contact = np.array([1.0, 0.0]) if self.stance == "l" else np.array([0.0, 1.0])

    # ------------------------------------------------------------------ pose output
    def _lower_target(self, est: EstState, info: dict) -> LowerTarget:
        lg = self.lg
        sd = self.stance
        # pelvis yaw: mean of the feet headings (smooth through a turn)
        if self.mode == "step" and self.t_mode <= self.t_ss():
            sw = "r" if sd == "l" else "l"
            psi_l = self.sw_pos[2] if sw == "l" else self.feet["l"][2]
            psi_r = self.sw_pos[2] if sw == "r" else self.feet["r"][2]
        else:
            psi_l, psi_r = self.feet["l"][2], self.feet["r"][2]
        yaw_target = 0.5 * (psi_l + psi_r)
        self.pelvis_yaw = yaw_target
        feet = {s: self.feet[s].copy() for s in "lr"}
        z = {"l": 0.0, "r": 0.0}
        if self.mode == "step" and self.t_mode <= self.t_ss():
            sw = "r" if sd == "l" else "l"
            feet[sw] = self.sw_pos.copy()
            z[sw] = self.sw_height
        ankle = {s: np.array([feet[s][0], feet[s][1], lg.ankle_h + z[s]]) for s in "lr"}
        Rm = R2(yaw_target)
        pel_xy = self.v_c + self.cfg.lead_s * self.v_v - Rm @ self.com_off - self.bias - self.cfg.kp_c * self.err_c - self.cfg.kd_c * self.err_v
        pelvis = np.array([pel_xy[0], pel_xy[1], self.pelvis_z])
        return LowerTarget(pelvis, yaw_target, 0.0, ankle, {s: feet[s][2] for s in "lr"}, self.contact.copy(), self.mode, info)

    def solve_legs(self, tgt: LowerTarget, q_ref: np.ndarray) -> np.ndarray:
        """Joint vector from a LowerTarget: IK for the legs, `q_ref` for everything else; refines the COM offset (2 passes)."""
        m = self.m
        kin = m.kin
        q = q_ref.copy()
        pel = tgt.pelvis.copy()
        quat = quat_from_yaw_pitch(0.0, 0.0)[0]
        for it in range(2):
            out, ok = lower_body(kin, pel[None], np.array([tgt.yaw]), np.array([tgt.pitch]), tgt.ankle["l"][None], tgt.ankle["r"][None],
                                 np.array([tgt.foot_yaw["l"]]), np.array([tgt.foot_yaw["r"]]))
            for n, v in out.items():
                if n in m.index:
                    q[m.index[n]] = float(v[0])
            if it == 0:
                # COM offset relative to the pelvis, in the pelvis-yaw frame, from the commanded posture
                qu = quat_from_yaw_pitch(tgt.yaw, 0.0)[0]
                com = kin.com(np.clip(q, m.lo, m.hi), np.zeros(3), qu)
                self.com_off = R2(tgt.yaw).T @ com[:2]
                pel[:2] = self.v_c + self.cfg.lead_s * self.v_v - R2(tgt.yaw) @ self.com_off - self.bias - self.cfg.kp_c * self.err_c - self.cfg.kd_c * self.err_v
        tgt.pelvis = pel
        self.ik_ok = bool(np.all(ok))
        return q

    def hold_reseed(self, est: EstState) -> None:
        """Back to hold with the feet where they are and the virtual COM re-seeded from the measurement (after a reference playback)."""
        self.mode = "hold"
        self.t_mode = 0.0
        self.contact = np.array([0.5, 0.5])
        self.stop_step = True
        c, v = self._measured_com(est)
        self.v_c, self.v_v = c, v

    def initial_pose(self, q_rest: np.ndarray) -> tuple:
        """(q, pelvis_xyz): the balanced standing pose of the planner's current feet with the COM over the support centre."""
        mid = self._support_centre({"l": 0.5, "r": 0.5})
        self.v_c, self.v_v = mid.copy(), np.zeros(2)
        self.cop = mid.copy()
        dummy = self._lower_target(None, {})
        q = self.solve_legs(dummy, q_rest.copy())
        return q, dummy.pelvis.copy()
