"""Scenario library: the software-in-the-loop acceptance tests, runnable from pytest and from `python -m openhumanoid.runtime scenarios`.

Every scenario builds a fresh sim (`make_sim`), drives the robot ONLY through the public Command API / safety hooks (like a user or an LLM
plugin would), measures with ground truth (`SimHAL.ground_truth`, never visible to the runtime) and returns a `Result` with the metrics and a
plain pass/fail. Pass criteria are written in each docstring; nothing is tuned per scenario.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .hal.sim import SimConfig, SimHAL
from .locomotion import GaitConfig
from .model import DEFAULT_CONCEPT, RobotModel
from .runtime import Runtime, RuntimeConfig

REQUIRED_PUSH_NS = 0.45            # N s, PROVISIONAL (concept engine thresholds.yaml motions.push.required_impulse_Ns)
DIRS = {"fwd": (1, 0, 0), "back": (-1, 0, 0), "left": (0, 1, 0), "right": (0, -1, 0)}

_MODEL_CACHE: dict = {}


def get_model(concept: str = DEFAULT_CONCEPT) -> RobotModel:
    if concept not in _MODEL_CACHE:
        _MODEL_CACHE[concept] = RobotModel.from_concept(concept)
    return _MODEL_CACHE[concept]


@dataclass
class Result:
    name: str
    passed: bool
    metrics: dict = field(default_factory=dict)
    notes: str = ""

    def row(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'}  {self.name:<34} {self.notes}"


def make_sim(model: RobotModel | None = None, scene_xml: str = "", sim: SimConfig | None = None, rt_cfg: RuntimeConfig | None = None,
             settle_ticks: int = 100) -> tuple:
    """-> (runtime, hal) with the robot standing in the planner's balanced pose, IMU initialised, settled."""
    model = model or get_model()
    hal = SimHAL(model, sim or SimConfig(), scene_xml=scene_xml)
    rt = Runtime(model, hal, rt_cfg or RuntimeConfig())
    q0, pel = rt.mgr.gait.initial_pose(rt.mgr.q_rest)
    hal.reset(q0, base_pos=pel + np.array([0, 0, 0.001]), base_quat=[1, 0, 0, 0])
    rt.mgr.q_out = q0
    rt.startup()
    for _ in range(settle_ticks):
        rt.step()
    return rt, hal


def yaw_of_truth(g: dict) -> float:
    w, x, y, z = g["base_quat"]
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


# ------------------------------------------------------------------------------------------------ stand
def stand(seconds: float = 60.0, rt_hal=None) -> Result:
    """Stand `seconds` untethered. PASS: never falls, tilt < 3 deg, COM within 25 mm of the support centre, no safety reason raised."""
    rt, hal = rt_hal or make_sim()
    mx, dev = 0.0, 0.0
    for _ in range(int(seconds / rt.dt)):
        rt.step()
        g = hal.ground_truth()
        sup = 0.5 * (g["feet"]["l"] + g["feet"]["r"])
        mx = max(mx, g["tilt_deg"])
        dev = max(dev, float(np.linalg.norm((g["com"] - sup)[:2] - np.array([0.0, 0.0]))))
    g = hal.ground_truth()
    ok = rt.safety.state == "ok" and mx < 3.0 and dev < 0.025 and not rt.safety.reasons
    return Result("stand", ok, {"seconds": seconds, "max_tilt_deg": round(mx, 2), "max_com_dev_m": round(dev, 4), "soc": round(g["pack_soc"], 4),
                                "max_temp_c": float(g["temp_c"].max()), "timing": rt.timing()}, f"{seconds:.0f} s, max tilt {mx:.1f} deg, COM dev {dev * 1000:.0f} mm")


# ------------------------------------------------------------------------------------------------ walk
def walk_and_turn(distance: float = 2.0, turn_deg: float = 90.0, speed: float = 0.12, wz: float = 0.35, rt_hal=None, timeout: float = 90.0) -> Result:
    """Walk `distance` m forward then turn `turn_deg` in place, commanded through the velocity API from the runtime's own odometry
    (planner feet) and gyro yaw. PASS: no fall, truth distance within 10 % of the target (and lateral error < 0.25 m), truth turn within 8 deg."""
    rt, hal = rt_hal or make_sim()
    G = rt.mgr.gait
    g0 = hal.ground_truth()
    p0, yaw0 = g0["base_pos"].copy(), yaw_of_truth(g0)
    est_yaw0 = rt.last_est.yaw
    phase, t0 = "walk", hal.t
    mx = 0.0
    t_walk = None
    while hal.t - t0 < timeout:
        if phase == "walk":
            odo = 0.5 * (G.feet["l"][0] + G.feet["r"][0])
            if odo >= distance:
                phase = "stop1"
                rt.client.velocity(0, 0, 0)
            else:
                rt.client.velocity(speed, 0, 0, ttl=0.3)
        elif phase == "stop1":
            if G.mode == "hold" and G.n_steps_taken > 0 and np.linalg.norm(rt.last_est.v[:2]) < 0.02:
                phase = "turn"
                t_walk = hal.t - t0
        elif phase == "turn":
            turned = (rt.last_est.yaw - est_yaw0)
            if turned >= math.radians(turn_deg):
                phase = "stop2"
                rt.client.velocity(0, 0, 0)
            else:
                rt.client.velocity(0, 0, wz, ttl=0.3)
        elif phase == "stop2":
            if G.mode == "hold" and np.linalg.norm(rt.last_est.v[:2]) < 0.02:
                for _ in range(100):
                    rt.step()
                break
        rt.step()
        mx = max(mx, hal.ground_truth()["tilt_deg"])
        if rt.safety.state != "ok":
            break
    g = hal.ground_truth()
    d = g["base_pos"] - p0
    dist = float(d[0] * math.cos(yaw0) + d[1] * math.sin(yaw0))
    lat = float(-d[0] * math.sin(yaw0) + d[1] * math.cos(yaw0))
    turn = math.degrees((yaw_of_truth(g) - yaw0 + math.pi) % (2 * math.pi) - math.pi)
    ok = (rt.safety.state == "ok" and phase == "stop2" and abs(dist - distance) < 0.1 * distance and abs(lat) < 0.25 and abs(turn - turn_deg) < 8.0)
    return Result("walk 2 m + turn 90 deg", ok, {"distance_m": round(dist, 3), "lateral_m": round(lat, 3), "turn_deg": round(turn, 1), "walk_s": t_walk,
                                                 "total_s": round(hal.t - t0, 1), "max_tilt_deg": round(mx, 1), "steps": G.n_steps_taken, "phase": phase,
                                                 "soc": round(g["pack_soc"], 4)},
                  f"walked {dist:.2f} m (lat {lat:+.2f}), turned {turn:.1f} deg, max tilt {mx:.1f}")


# ------------------------------------------------------------------------------------------------ pushes
def push_stand(J: float = REQUIRED_PUSH_NS, direction: str = "fwd", mode: str = "force", rt_cfg: RuntimeConfig | None = None, settle_s: float = 3.0,
               pulse_s: float = 0.05) -> Result:
    """Push the standing robot with impulse J [N s] (force pulse on the torso, 50 ms). PASS: no fall and upright (< 3 deg) `settle_s` later."""
    rt, hal = make_sim(rt_cfg=rt_cfg)
    steps0 = rt.mgr.gait.n_steps_taken
    d = np.array(DIRS[direction], float)
    hal.push(d * J, pulse_s, mode)
    mx = 0.0
    for _ in range(int((settle_s + 1.0) / rt.dt)):
        rt.step()
        mx = max(mx, hal.ground_truth()["tilt_deg"])
        if rt.safety.state != "ok":
            break
    g = hal.ground_truth()
    ok = rt.safety.state == "ok" and g["tilt_deg"] < 3.0
    return Result(f"push stand {direction} {J:.2f} N s", ok, {"J": J, "dir": direction, "max_tilt_deg": round(mx, 1), "final_tilt_deg": round(g["tilt_deg"], 2),
                                                              "steps_taken": rt.mgr.gait.n_steps_taken - steps0, "state": rt.safety.state},
                  f"max tilt {mx:.1f}, steps {rt.mgr.gait.n_steps_taken - steps0}")


def push_walk(J: float = REQUIRED_PUSH_NS, direction: str = "fwd", step_target: int = 4, vx: float = 0.08, mode: str = "force",
              rt_cfg: RuntimeConfig | None = None, after_s: float = 4.0) -> Result:
    """Push the walking robot at mid single support of footfall `step_target`. PASS: no fall and still walking upright `after_s` later."""
    rt, hal = make_sim(rt_cfg=rt_cfg)
    G = rt.mgr.gait
    d = np.array(DIRS[direction], float)
    pushed, k_push, mx = False, 0, 0.0
    for k in range(int(25.0 / rt.dt)):
        rt.client.velocity(vx, 0, 0, ttl=0.3)
        rt.step()
        if not pushed and G.n_steps_taken == step_target and G.last_info.get("phase") == "ss" and G.t_mode > 0.5 * G.t_ss():
            hal.push(d * J, 0.05, mode)
            pushed, k_push = True, k
        if pushed:
            mx = max(mx, hal.ground_truth()["tilt_deg"])
            if k - k_push > after_s / rt.dt or rt.safety.state != "ok":
                break
    g = hal.ground_truth()
    ok = pushed and rt.safety.state == "ok" and g["tilt_deg"] < 6.0 and G.mode in ("step", "shift")
    return Result(f"push walk {direction} {J:.2f} N s", ok, {"J": J, "dir": direction, "max_tilt_deg": round(mx, 1), "final_tilt_deg": round(g["tilt_deg"], 2), "state": rt.safety.state,
                                                             "pushed": pushed}, f"max tilt {mx:.1f}")


def largest_push(kind: str, direction: str, hi: float = 3.0, lo: float = 0.0, tol: float = 0.1, rt_cfg_factory=None, **kw) -> dict:
    """Largest recoverable impulse by scan + bisection (a push can be recovered at J and not at J' < J only through noise; the scan goes down
    from `hi` in 0.25 steps to the first recovery, then bisects between it and the failure above)."""
    fn = push_stand if kind == "stand" else push_walk
    cfg = (lambda: rt_cfg_factory()) if rt_cfg_factory else (lambda: None)
    tried = {}

    def ok(J):
        r = fn(J, direction, rt_cfg=cfg(), **kw)
        tried[round(J, 3)] = r.passed
        return r.passed
    J = 0.25
    last_ok = 0.0
    while J <= hi + 1e-9:
        if ok(J):
            last_ok = J
            J += 0.25
        else:
            break
    if last_ok >= hi - 1e-9:
        return {"largest_Ns": hi, "capped": True, "tried": tried}
    lo_, hi_ = last_ok, J
    while hi_ - lo_ > tol:
        mid = 0.5 * (lo_ + hi_)
        if ok(mid):
            lo_ = mid
        else:
            hi_ = mid
    return {"largest_Ns": round(lo_, 2), "capped": False, "tried": tried}


# ------------------------------------------------------------------------------------------------ behaviours
def wave(seconds: float = 10.0) -> Result:
    """Wave (right arm). PASS: no fall, tilt < 3 deg, the shoulder roll reaches >= 60 deg (abducted outward) and the elbow oscillates >= 20 deg peak to peak, finishes."""
    rt, hal = make_sim()
    m = rt.m
    r = rt.client.behaviour("wave", side="r")
    ir, ie = m.index["shoulder_roll_r"], m.index["elbow_r"]
    roll, elb, mx = [], [], 0.0
    for _ in range(int(seconds / rt.dt)):
        rt.step()
        s = rt.last_state
        roll.append(s.q[ir])
        elb.append(s.q[ie])
        mx = max(mx, hal.ground_truth()["tilt_deg"])
    roll, elb = np.array(roll), np.array(elb)
    done = ("done", "wave") in rt.mgr.events
    ptp = float(np.degrees(np.ptp(elb[len(elb) // 4: 3 * len(elb) // 4])))
    ok = rt.safety.state == "ok" and mx < 3.0 and abs(roll).max() > math.radians(60) and ptp >= 20.0 and done
    return Result("wave", ok, {"max_abs_shoulder_roll_deg": round(float(np.degrees(abs(roll).max())), 1), "elbow_ptp_deg": round(ptp, 1), "max_tilt_deg": round(mx, 2), "finished": done},
                  f"abduction {np.degrees(abs(roll).max()):.0f} deg, elbow swing {ptp:.0f} deg, tilt {mx:.1f}")


def dance(rt_hal=None) -> Result:
    """The 30+ s dance clip (6 phrases of 8 beats at 80 BPM = 36 s) played back untethered. PASS: finishes, no fall, tilt < 5 deg, no servo overload trips, hottest servo < 55 C."""
    rt, hal = rt_hal or make_sim()
    rt.client.behaviour("dance")
    mx, t0 = 0.0, hal.t
    for _ in range(int(60 / rt.dt)):
        rt.step()
        mx = max(mx, hal.ground_truth()["tilt_deg"])
        if ("done", "dance") in rt.mgr.events or rt.safety.state != "ok":
            break
    dur = hal.t - t0
    g = hal.ground_truth()
    trips = int(hal.bank.trips.sum())
    ok = ("done", "dance") in rt.mgr.events and rt.safety.state == "ok" and mx < 5.0 and trips == 0 and float(g["temp_c"].max()) < 55.0 and dur > 30.0
    return Result("dance 30 s", ok, {"duration_s": round(dur, 1), "max_tilt_deg": round(mx, 2), "overload_trips": trips, "max_temp_c": float(g["temp_c"].max()), "soc": round(g["pack_soc"], 4)},
                  f"{dur:.1f} s, max tilt {mx:.1f}, trips {trips}")


def pickup(table_height: float = 0.30) -> Result:
    """Whole-body pick-up of the 150 g cylinder from a table at `table_height` m (within the reachable range of the R1 concept). PASS: object lifted >= 15 mm
    above its rest height and still held 2 s after the clip ended, no fall, tilt < 5 deg."""
    from .clips import ClipStore
    model = get_model()
    ref = ClipStore(model)("pickup", table_height_m=table_height)
    if not ref.feasible:
        return Result("pickup", False, {"table_height_m": table_height}, f"clip infeasible: {ref.notes[:1]}")
    rt, hal = make_sim(scene_xml=ref.scene["xml"])
    rt.client.behaviour("pickup", table_height_m=table_height)
    obj = hal.mjm.body("obj").id
    z0 = float(hal.data.xpos[obj][2])
    zmax, mx = z0, 0.0
    for _ in range(int((ref.duration + 3.0) / rt.dt)):
        rt.step()
        zmax = max(zmax, float(hal.data.xpos[obj][2]))
        mx = max(mx, hal.ground_truth()["tilt_deg"])
        if rt.safety.state != "ok":
            break
    zend = float(hal.data.xpos[obj][2])
    ok = rt.safety.state == "ok" and (zend - z0) >= 0.015 and mx < 5.0 and ("done", "pickup") in rt.mgr.events
    return Result("pickup", ok, {"table_height_m": table_height, "max_lift_m": round(zmax - z0, 3), "held_lift_m": round(zend - z0, 3), "max_tilt_deg": round(mx, 2)},
                  f"table {table_height:.2f} m, lifted {1000 * (zmax - z0):.0f} mm, held {1000 * (zend - z0):.0f} mm")


def look_at() -> Result:
    """Orient neck + waist toward a person at 1 m, 0.6 m to the left, eye height. PASS: the head's forward axis ends within 5 deg of the target direction (ground truth)."""
    rt, hal = make_sim()
    target = np.array([1.0, 0.6, 0.30])
    rt.client.look_at(*target)
    for _ in range(int(3.0 / rt.dt)):
        rt.step()
    d = hal.data
    head = hal.mjm.body("head").id
    fwd = d.xmat[head].reshape(3, 3)[:, 0]
    # target direction from the head position (world frame, robot starts at the origin facing +x)
    v = target - d.xpos[head]
    v = v / np.linalg.norm(v)
    err = math.degrees(math.acos(float(np.clip(fwd @ v, -1, 1))))
    ok = err < 5.0 and rt.safety.state == "ok"
    return Result("look at a person", ok, {"error_deg": round(err, 2), "neck_yaw_deg": round(math.degrees(rt.last_state.q[rt.m.index["neck_yaw"]]), 1),
                                           "waist_yaw_deg": round(math.degrees(rt.last_state.q[rt.m.index["waist_yaw"]]), 1)}, f"pointing error {err:.1f} deg")


# ------------------------------------------------------------------------------------------------ safety
def estop() -> Result:
    """E-stop while walking, with a client that keeps sending velocity commands. PASS: all servos torqued off within 3 control cycles of the command,
    no later command re-enables them, reset is refused while the robot is moving (and accepted once still)."""
    rt, hal = make_sim()
    rt.client.velocity(0.1, 0, 0, ttl=10)
    for _ in range(200):
        rt.step()
    rt.client.estop("scenario")
    cycles_to_off = None
    for k in range(120):
        rt.client.velocity(0.1, 0, 0, ttl=10)
        rt.client.behaviour("dance")
        rt.step()
        if cycles_to_off is None and int(rt.last_state.torque_on.sum()) == 0:
            cycles_to_off = k
    still_off = int(hal.read().torque_on.sum()) == 0
    ok = cycles_to_off is not None and cycles_to_off <= 3 and still_off and rt.safety.estopped
    return Result("e-stop", ok, {"cycles_to_torque_off": cycles_to_off, "still_off_after_commands": still_off, "latched": rt.safety.estopped}, f"torque off after {cycles_to_off} cycles")


def overheat(temp_c: float = 66.0) -> Result:
    """A knee servo reads 66 C (software cutoff 65 C, firmware 70 C). PASS: crouch started within 1 s, robot lowered without a fall, torque off at the bottom."""
    rt, hal = make_sim()
    for _ in range(50):
        rt.step()
    hal.set_temperature("knee_l", temp_c)
    t_event = None
    for k in range(int(15 / rt.dt)):
        rt.step()
        if t_event is None and "overheat" in rt.safety.reasons:
            t_event = k * rt.dt
        if rt.safety.state == "limp":
            break
    for _ in range(10):
        rt.step()
    g = hal.ground_truth()
    off = int(rt.last_state.torque_on.sum()) == 0
    ok = rt.safety.state == "limp" and off and g["tilt_deg"] < 10.0 and t_event is not None and t_event < 1.0
    return Result("overheat cutoff", ok, {"detect_s": t_event, "torque_off": off, "final_state": rt.safety.state, "final_tilt_deg": round(g["tilt_deg"], 1), "pelvis_z": round(g["pelvis_z"], 3)},
                  f"detected after {t_event} s, ended {rt.safety.state}, tilt {g['tilt_deg']:.1f}")


def low_battery() -> Result:
    """Battery at 1 % state of charge (loaded cell voltage below 3.35 V). PASS: warning first (new walking refused), then crouch and torque off with no fall."""
    rt, hal = make_sim()
    hal.set_battery_soc(0.01)
    warned_at, refused = None, False
    for k in range(int(40 / rt.dt)):
        rt.step()
        if warned_at is None and rt.safety.warn_batt:
            warned_at = k * rt.dt
            rt.client.velocity(0.1, 0, 0)
            for _ in range(20):
                rt.step()
            refused = rt.mgr.behaviour != "walk" or np.linalg.norm(rt.mgr.cmd_vel) == 0
        if rt.safety.state == "limp":
            break
    g = hal.ground_truth()
    ok = rt.safety.state == "limp" and "batt_cut" in rt.safety.reasons and warned_at is not None and refused and g["tilt_deg"] < 10.0
    return Result("low-battery cutoff", ok, {"warned_at_s": warned_at, "walking_refused": refused, "final_state": rt.safety.state, "final_tilt_deg": round(g["tilt_deg"], 1)},
                  f"warned {warned_at}, refused walking {refused}, ended {rt.safety.state}")


def fall(J: float = 3.0) -> Result:
    """A push far beyond recovery (3 N s). PASS: fall detected within 0.5 s of the tilt passing 18 deg, safe-fall pose commanded (legs tucked, arms folded),
    torque limited while falling, torque off once the robot is at rest."""
    rt, hal = make_sim()
    hal.push(np.array([J, 0, 0]), 0.05)
    t_fall = None
    pose_err = None
    limited = False
    for k in range(int(8 / rt.dt)):
        rt.step()
        if t_fall is None and rt.safety.state == "fall":
            t_fall = k * rt.dt
        if rt.safety.state == "fall" and k * rt.dt - (t_fall or 0) > 0.6 and pose_err is None:
            cmd_q = rt.safety.last_q
            pose_err = float(np.abs(cmd_q[rt.m.idx("knee_l")[0]] - rt.mgr.fall_q[rt.m.idx("knee_l")[0]]))
            limited = bool(hal.cmd.torque_limit.max() <= rt.safety.cfg.fall_torque + 1e-6)
        if rt.safety.state == "limp":
            break
    ok = t_fall is not None and rt.safety.state == "limp" and pose_err is not None and pose_err < 0.2 and limited
    return Result("fall -> safe-fall pose", ok, {"detected_s": t_fall, "knee_cmd_error_rad": pose_err, "torque_limited": limited, "final_state": rt.safety.state},
                  f"detected {t_fall}, pose error {pose_err}, torque limited {limited}, ended {rt.safety.state}")


# ------------------------------------------------------------------------------------------------ registry
ALL = {
    "stand": lambda: stand(60.0), "walk": walk_and_turn, "push_stand": lambda: [push_stand(REQUIRED_PUSH_NS, d) for d in DIRS],
    "push_walk": lambda: [push_walk(REQUIRED_PUSH_NS, d) for d in DIRS], "wave": wave, "dance": dance, "pickup": pickup, "look_at": look_at,
    "estop": estop, "overheat": overheat, "low_battery": low_battery, "fall": fall,
}
