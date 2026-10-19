"""Behaviours and the behaviour manager.

The manager owns the walking/standing brain (`locomotion.Gait`), the ankle stabiliser, the upper-body overlays (look-at, wave, pose) and
the reference players (dance, pickup, crouch, safe-fall). It outputs a joint target and a torque limit; the safety layer filters it.

Behaviours:
  stand          Gait in hold: the DCM is regulated over the feet (ankle strategy through the kinematic COM target) and a capture step
                 is taken when the DCM leaves the support (push recovery).
  walk           Gait stepping to a velocity command (vx, vy, wz); stops itself with a square-up step when the command goes to zero.
  wave           upper-body overlay from the motion library (abducted arm, forearm oscillation), legs stay in stand.
  dance          full-body reference from the motion library, played back with the stabiliser on.
  pickup         full-body whole-body pick-up reference from the motion library (needs a table at the planned distance).
  look_at        neck/waist overlay toward a target in the body frame.
  pose           upper-body joint targets (named joints), clamped by the safety layer.
  crouch         controlled lowering used by the safety layer (low battery, overheat); ends limp.
  fall           the safe-fall pose.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..concept.kin import smoothstep5
from .estimator import EstState
from .hal.base import HalState
from .locomotion import Gait, GaitConfig
from .model import RobotModel

LEG_BASES = ("hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll")


@dataclass
class StabiliserConfig:
    kp_pitch: float = 0.35
    kd_pitch: float = 0.10
    kp_roll: float = 0.35
    kd_roll: float = 0.12
    ki_pitch: float = 1.2             # 1/s integral on the lean (removes the load-proportional servo sag)
    ki_roll: float = 1.2
    int_limit: float = 0.25
    limit: float = 0.35               # max ankle correction [rad]


class Stabiliser:
    """IMU orientation PD through the ankles of the feet that carry weight (the ankle strategy's inner loop)."""

    def __init__(self, model: RobotModel, cfg: StabiliserConfig | None = None):
        self.m = model
        self.cfg = cfg or StabiliserConfig()
        self.ip = {s: model.index.get(f"ankle_pitch_{s}", -1) for s in "lr"}
        self.ir = {s: model.index.get(f"ankle_roll_{s}", -1) for s in "lr"}
        self.last = np.zeros(2)
        self.integ = np.zeros(2)
        self.dt = 0.01

    def apply(self, q: np.ndarray, est: EstState, contact: np.ndarray, pitch_des: float = 0.0, roll_des: float = 0.0) -> np.ndarray:
        c = self.cfg
        loaded = min(1.0, 2.0 * float(max(contact)))
        self.integ[0] = np.clip(self.integ[0] + loaded * c.ki_pitch * (est.pitch - pitch_des) * self.dt, -c.int_limit, c.int_limit)
        self.integ[1] = np.clip(self.integ[1] + loaded * c.ki_roll * (est.roll - roll_des) * self.dt, -c.int_limit, c.int_limit)
        dp = c.kp_pitch * (est.pitch - pitch_des) + c.kd_pitch * est.gyro[1] + self.integ[0]
        dr = c.kp_roll * (est.roll - roll_des) + c.kd_roll * est.gyro[0] + self.integ[1]
        dp = float(np.clip(dp, -c.limit, c.limit))
        dr = float(np.clip(dr, -c.limit, c.limit))
        self.last = np.array([dp, dr])
        q = q.copy()
        for i, s in enumerate("lr"):
            g = min(1.0, 2.0 * float(contact[i]))
            if self.ip[s] >= 0:
                q[self.ip[s]] += g * dp
            if self.ir[s] >= 0:
                q[self.ir[s]] += g * dr
        return q


class RefPlayer:
    """Plays a concept-engine `Reference` (joint vectors at ref.dt) with a blend-in from the current command."""

    def __init__(self, ref, q_start: np.ndarray, blend_s: float = 0.8, tail_s: float = 0.0):
        self.ref = ref
        self.q_start = q_start.copy()
        self.blend_s = blend_s
        self.t = 0.0
        self.total = ref.duration + tail_s
        self.done = False

    def q(self, dt: float) -> np.ndarray:
        r = self.ref
        t = self.t
        k = min(t / r.dt, len(r.q) - 1.0)
        i0 = int(math.floor(k))
        i1 = min(i0 + 1, len(r.q) - 1)
        f = k - i0
        qr = (1 - f) * r.q[i0] + f * r.q[i1]
        b = float(smoothstep5(t / self.blend_s)) if self.blend_s > 0 else 1.0
        out = (1 - b) * self.q_start + b * qr
        self.t += dt
        if self.t >= self.total:
            self.done = True
        return out


@dataclass
class Status:
    mode: str
    behaviour: str
    detail: dict = field(default_factory=dict)


class BehaviourManager:
    def __init__(self, model: RobotModel, dt: float, gait_cfg: GaitConfig | None = None, stab_cfg: StabiliserConfig | None = None,
                 clip_provider=None):
        self.m = model
        self.dt = dt
        self.gait = Gait(model, gait_cfg)
        self.stab = Stabiliser(model, stab_cfg)
        self.stab.dt = dt
        self.clips = clip_provider
        self.q_rest = model.stand_q(self.gait.flex)
        self.q_out = self.q_rest.copy()
        self.behaviour = "stand"
        self.player: RefPlayer | None = None
        self.player_kind = ""
        self.overlay_wave: RefPlayer | None = None
        self.wave_joints = np.zeros(model.n, bool)
        self.look: np.ndarray | None = None
        self.look_state = np.zeros(3)
        self.pose_targets: dict = {}
        self.cmd_vel = np.zeros(3)
        self.contact = np.array([0.5, 0.5])
        self.torque_limit = np.ones(model.n)
        self.tl_grip = np.array([0.15 if n.startswith("gripper") else 1.0 for n in model.names])
        self.mode = "stand"
        self.events: list = []
        self.sleeping = False
        self._crouch_ref = None
        self._fall_q = self._build_fall_pose()
        self.done_cb = None
        self.arm_swing_state = np.zeros(2)
        self.hold_after = None
        self.carry = None
        self.carry_mask = None
        self.trim = np.zeros(model.n)
        self.damp_kd = 0.03
        self.damp_mask = np.array([0.0 if n.startswith('gripper') else 1.0 for n in model.names])
        self._tgt_prev = None
        self.trim_mask = np.array([0.0 if (n.split('_')[0] in ('hip', 'knee', 'ankle', 'gripper')) else 1.0 for n in model.names])
        self.trim_ki = 3.0                 # 1/s: removes the servo's load-proportional steady-state error (stand-in for the servo I-coefficient)
        self.trim_leak = 0.05
        self.trim_limit = 0.2
        self.leg_mask = np.array([n.split("_")[0] in ("hip", "knee", "ankle") for n in model.names])

    # ------------------------------------------------------------------ poses
    def _build_fall_pose(self) -> np.ndarray:
        """Safe-fall pose: legs tucked, arms folded against the body, head neutral. Expressed in joint space."""
        m = self.m
        q = m.stand_q(self.gait.flex).copy()
        tuck = {"hip_pitch": -1.25, "knee": 1.75, "ankle_pitch": -0.45, "hip_roll": 0.0, "hip_yaw": 0.0, "ankle_roll": 0.0}
        for s in "lr":
            for b, v in tuck.items():
                if f"{b}_{s}" in m.index:
                    q[m.index[f"{b}_{s}"]] = v
        for s, sg in (("l", 1.0), ("r", -1.0)):
            for b, v in (("shoulder_pitch", 0.0), ("shoulder_roll", sg * 0.12), ("elbow", -1.4)):
                if f"{b}_{s}" in m.index:
                    q[m.index[f"{b}_{s}"]] = v
        for nm in ("waist_yaw", "neck_yaw", "neck_pitch"):
            if nm in m.index:
                q[m.index[nm]] = 0.0
        return m.clamp(q)

    @property
    def fall_q(self) -> np.ndarray:
        return self._fall_q

    # ------------------------------------------------------------------ commands (called from the runtime between cycles)
    def set_velocity(self, vx: float, vy: float, wz: float) -> None:
        self.cmd_vel = np.array([vx, vy, wz], float)

    def start(self, name: str, params: dict | None, est: EstState | None = None) -> tuple:
        """Returns (ok, message)."""
        params = params or {}
        if self.mode in ("crouch", "fall", "limp"):
            return False, f"refused: robot is in {self.mode}"
        if name == "stand":
            if params.get("release"):
                self.carry = None
            self._stop_ref()
            self.behaviour = "stand"
            self.cmd_vel[:] = 0
            return True, "standing"
        if name == "walk":
            self._stop_ref()
            self.behaviour = "walk"
            return True, "walking (send velocity commands)"
        if name == "wave":
            kin = self.m.kin
            from ..concept.motions.posture import wave
            ref = self.clips("wave", side=params.get("side", "r")) if self.clips else wave(kin, params.get("side", "r"))
            idx = [i for i, nm in enumerate(self.m.names) if not nm.split("_")[0] in ("hip", "knee", "ankle")]
            self.wave_joints = np.zeros(self.m.n, bool)
            self.wave_joints[idx] = True
            self.overlay_wave = RefPlayer(ref, self.q_out, blend_s=0.5)
            return True, "waving"
        if name in ("dance", "pickup"):
            if self.gait.walking or np.linalg.norm(self.cmd_vel) > 1e-3:
                return False, "refused: stop walking first"
            ref = self.clips(name, **params) if self.clips else None
            if ref is None:
                return False, f"no clip for {name}"
            if not ref.feasible:
                return False, f"{name} reference infeasible: {ref.notes}"
            self.player = RefPlayer(ref, self.q_out, blend_s=0.8, tail_s=0.6)
            self.player_kind = name
            self.behaviour = name
            return True, f"{name} started ({ref.duration:.1f} s)"
        return False, f"unknown behaviour {name}"

    def stop(self, name: str | None = None) -> None:
        if name in (None, "wave"):
            self.overlay_wave = None
        if name in (None, "dance", "pickup"):
            self._stop_ref()
            if name in (None, "pickup"):
                self.carry = None
        if name in (None, "walk"):
            self.cmd_vel[:] = 0
            if self.behaviour == "walk":
                self.behaviour = "stand"
        if name is None:
            self.look = None
            self.pose_targets = {}

    def _stop_ref(self) -> None:
        self.player = None
        self.player_kind = ""
        if self.behaviour in ("dance", "pickup"):
            self.behaviour = "stand"

    def look_at(self, target_body: np.ndarray | None) -> None:
        self.look = None if target_body is None else np.asarray(target_body, float)

    def set_pose(self, joints: dict) -> None:
        self.pose_targets = {k: float(v) for k, v in joints.items() if k in self.m.index}

    # ------------------------------------------------------------------ safety hand-over
    def enter(self, mode: str, est: EstState) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        if mode == "crouch":
            ref = self.clips("crouch")
            self.player = RefPlayer(ref, self.q_out, blend_s=0.6)
            self.player_kind = "crouch"
            self.overlay_wave = None
        elif mode == "fall":
            self.player = None
            self.overlay_wave = None
        elif mode == "stand":
            pass

    # ------------------------------------------------------------------ the cycle
    def update(self, est: EstState, s: HalState) -> tuple:
        """-> (q_target, torque_limit, contact_hint)."""
        dt = self.dt
        m = self.m
        self._s_now = s
        if self.mode == "fall":
            self.contact = np.array([0.0, 0.0])
            return self._fall_q.copy(), np.ones(m.n), self.contact
        if self.mode == "crouch":
            q = self.player.q(dt)
            q = self.stab.apply(q, est, np.array([0.5, 0.5]))
            self.q_out = q
            return q, np.ones(m.n) * self.tl_grip, np.array([0.5, 0.5])

        # ---- velocity -> gait
        walking_ok = self.behaviour == "walk" and self.player is None
        if walking_ok:
            self.gait.command(*self.cmd_vel)
        else:
            self.gait.command(0.0, 0.0, 0.0)

        if self.player is not None:
            q = self._play_reference(est)
            contact = np.array([0.5, 0.5])
            tl = np.ones(m.n) * self.tl_grip
        else:
            tgt = self.gait.update(est, dt, allow_capture=True)
            q = self.gait.solve_legs(tgt, self.q_rest.copy())
            q = self._upper_body(q, est, tgt)
            contact = tgt.contact
            tl = np.ones(m.n) * self.tl_grip
        q = self._overlays(q, est)
        q = self._trim(q, s, contact)
        q = self.stab.apply(q, est, contact)
        q = self._damp(q, s)
        self.q_out = q
        self.contact = contact
        return q, tl, contact

    def _damp(self, q: np.ndarray, s: HalState) -> np.ndarray:
        """Joint-level damping injection: q_cmd -= Kd * measured speed. The identified servo model (BAM) has no D term and a 6.5 Hz, zeta ~ 0.4
        resonance (armature 0.0234 kg m^2); on hardware this is the Feetech D coefficient. The command is not fed back into the plan (q_out keeps it)."""
        return q - self.damp_kd * s.dq * self.damp_mask

    def _trim(self, q: np.ndarray, s: HalState, contact: np.ndarray) -> np.ndarray:
        """Slow integrator on the joints' load-proportional steady-state error: trim += ki (previous target - measured). The firmware is
        P-only (the Feetech I coefficient is the hardware equivalent); without it a held arm sags by torque / stiffness. Upper-body and
        gripper-free joints only; the legs rely on the gait's COM-bias estimate and the ankle integrator."""
        if self._tgt_prev is not None:
            err = (self._tgt_prev - s.q) * self.trim_mask
            self.trim = np.clip(self.trim + self.dt * (self.trim_ki * err - self.trim_leak * self.trim), -self.trim_limit, self.trim_limit)
        self._tgt_prev = q.copy()
        return q + self.trim * self.trim_mask

    def _play_reference(self, est: EstState) -> np.ndarray:
        p = self.player
        q = p.q(self.dt)
        if p.done:
            kind = self.player_kind
            if kind == "pickup":
                self.carry = np.where(self.leg_mask > 0, 0.0, q)         # keep holding the object: the upper body stays where the clip ended
                self.carry_mask = self.leg_mask == 0
            self.player = None
            self.player_kind = ""
            self.behaviour = "stand"
            self.events.append(("done", kind))
            self.gait.hold_reseed(est)
        return q

    def _upper_body(self, q: np.ndarray, est: EstState, tgt) -> np.ndarray:
        """Arm swing from the foot positions while walking (concept convention), rest posture otherwise."""
        m = self.m
        g = self.gait
        if g.walking and g.cfg.arm_swing:
            xl, xr = tgt.ankle["l"][0], tgt.ankle["r"][0]
            sw = np.clip((xl - xr) / 0.06, -1, 1) * 0.35 * g.cfg.arm_swing
            self.arm_swing_state = 0.9 * self.arm_swing_state + 0.1 * np.array([sw, -sw])
        else:
            self.arm_swing_state *= 0.9
        for i, s in enumerate("lr"):
            k = m.index.get(f"shoulder_pitch_{s}")
            if k is not None:
                q[k] = self.q_rest[k] + self.arm_swing_state[i]
        if self.carry is not None:
            q[self.carry_mask] = self.carry[self.carry_mask]
        return q

    def _overlays(self, q: np.ndarray, est: EstState) -> np.ndarray:
        m = self.m
        out = q.copy()
        if self.pose_targets and self.player is None:
            for nm, v in self.pose_targets.items():
                if not nm.split("_")[0] in ("hip", "knee", "ankle"):
                    out[m.index[nm]] = v
        if self.overlay_wave is not None:
            qw = self.overlay_wave.q(self.dt)
            out[self.wave_joints] = qw[self.wave_joints]
            if self.overlay_wave.done:
                self.overlay_wave = None
                self.events.append(("done", "wave"))
        if self.look is not None and self.player is None:
            out = self._apply_look(out)
        elif self.player is None:
            for nm in ("neck_yaw", "neck_pitch", "waist_yaw"):
                if nm in m.index and nm not in self.pose_targets and self.overlay_wave is None:
                    i = m.index[nm]
                    out[i] = q[i]
        return out

    def _apply_look(self, q: np.ndarray) -> np.ndarray:
        m = self.m
        x, y, z = self.look
        yaw = math.atan2(y, max(x, 1e-6)) if x > 0 else math.atan2(y, x)
        head_z = 0.78 * m.robot.height                      # camera height above the floor: pelvis frame target compared to eye height
        dist = math.hypot(x, y)
        pitch = math.atan2(-(z - (head_z - 0.0)) , max(dist, 0.05))     # + = look down (neck_pitch +)
        pitch = -math.atan2(z - head_z, max(dist, 0.05))
        lim_n = m.hi[m.index["neck_yaw"]] if "neck_yaw" in m.index else 0.0
        waist_share = 0.0
        if "waist_yaw" in m.index:
            waist_share = float(np.clip(abs(yaw) - 1.0, 0.0, 1.0)) if abs(yaw) > 1.0 else 0.0
        tgt = np.array([yaw, pitch, 0.0])
        # smooth (first-order, 0.15 s)
        a = 1 - math.exp(-self.dt / 0.15)
        self.look_state += a * (tgt - self.look_state)
        yaw_s, pitch_s = self.look_state[0], self.look_state[1]
        if "waist_yaw" in m.index:
            wy = float(np.clip(yaw_s * 0.35, m.lo[m.index["waist_yaw"]] * 0.6, m.hi[m.index["waist_yaw"]] * 0.6))
            q[m.index["waist_yaw"]] = wy
            yaw_neck = yaw_s - wy
        else:
            yaw_neck = yaw_s
        if "neck_yaw" in m.index:
            q[m.index["neck_yaw"]] = float(np.clip(yaw_neck, m.lo[m.index["neck_yaw"]], m.hi[m.index["neck_yaw"]]))
        if "neck_pitch" in m.index:
            q[m.index["neck_pitch"]] = float(np.clip(pitch_s, m.lo[m.index["neck_pitch"]], m.hi[m.index["neck_pitch"]]))
        return q

    # ------------------------------------------------------------------ reporting
    def status(self) -> dict:
        g = self.gait
        return {"mode": self.mode, "behaviour": self.behaviour, "gait_mode": g.mode, "steps": g.n_steps_taken,
                "cmd_vel": [round(float(x), 3) for x in self.cmd_vel], "wave": self.overlay_wave is not None,
                "player": self.player_kind, "look_at": None if self.look is None else [round(float(x), 3) for x in self.look]}
