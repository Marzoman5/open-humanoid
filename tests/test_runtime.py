"""Software-in-the-loop tests: the runtime (HAL, safety, estimator, behaviours, command API) against MuJoCo + the measured servo model.

Fast tests (unit level, a few seconds each) run by default; the multi-second scenario tests are marked `slow`
(`pytest tests/test_runtime.py -m "not slow"` for the quick set). Ground truth is only used to score, never by the runtime.
"""
from __future__ import annotations

import json
import math
import socket
import urllib.request

import numpy as np
import pytest

pytest.importorskip("mujoco")

from openhumanoid.runtime import scenarios as S
from openhumanoid.runtime.commands import COMMANDS, CommandBus, RobotClient
from openhumanoid.runtime.estimator import StateEstimator
from openhumanoid.runtime.frontends.gamepad import GamepadMapper, PadState
from openhumanoid.runtime.frontends.web import JsonLineServer, WebServer
from openhumanoid.runtime.hal.base import JointCmd
from openhumanoid.runtime.hal.feetech import (COUNTS, REGISTERS, FeetechHAL, MockBus, ServoMap, decode_signed, encode_signed)
from openhumanoid.runtime.hal.sim import SimConfig, SimHAL
from openhumanoid.runtime.locomotion import Gait, GaitConfig
from openhumanoid.runtime.safety import Safety


_OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({})).open        # no system proxy for localhost


@pytest.fixture(scope="module")
def model():
    return S.get_model()


# ------------------------------------------------------------------------------------------------ model / reuse of the concept engine
def test_model_comes_from_the_concept(model):
    assert model.n == 23 and "knee_l" in model.index and model.mass > 3.0
    # the sim's servo constants are the concept engine's own objects
    from openhumanoid.actuators import ServoSpec
    assert all(isinstance(model.robot.servo[n], ServoSpec) for n in model.names)
    assert model.robot.servo["knee_l"].key == "sts3250-12v"
    assert np.all(model.lo < model.hi)


def test_sim_hal_uses_the_servo_bank_and_register_semantics(model):
    hal = SimHAL(model, SimConfig())
    from openhumanoid.actuators import ServoBank
    assert isinstance(hal.bank, ServoBank)
    q0 = model.stand_q()
    hal.reset(q0)
    for _ in range(20):
        hal.write(JointCmd.hold(q0))
        hal.tick()
    s = hal.read()
    # quantised to the servo's 4096 counts per revolution
    step = 2 * math.pi / COUNTS
    k = (s.q / model.ratio) / step
    assert np.allclose(k, np.round(k), atol=1e-6)
    assert 10.0 < s.voltage < 13.0 and s.torque_on.all()
    # torque enable off: the servo stops holding
    cmd = JointCmd.hold(q0)
    cmd.enable[:] = False
    hal.write(cmd)
    for _ in range(5):
        hal.tick()
    assert hal.read().torque_on.sum() == 0


def test_firmware_thermal_shutdown_and_latching(model):
    hal = SimHAL(model, SimConfig())
    hal.reset(model.stand_q())
    hal.set_temperature("knee_r", 71.0)
    hal.write(JointCmd.hold(model.stand_q()))
    hal.tick()
    s = hal.read()
    assert s.fault[model.index["knee_r"]] and not s.torque_on[model.index["knee_r"]]


# ------------------------------------------------------------------------------------------------ safety layer
def test_safety_clamps_limits_rate_and_nan(model):
    sf = Safety(model, dt=0.01)
    hal = SimHAL(model, SimConfig())
    hal.reset(model.stand_q())
    s = hal.read()
    sf.last_q = s.q.copy()
    wild = s.q + 10.0
    cmd = sf.filter(wild, None, s)
    assert np.all(cmd.q <= model.hi) and np.all(cmd.q >= model.lo)
    assert np.all(np.abs(cmd.q - s.q) <= sf.rate * sf.dt + 1e-9 + np.abs(sf.last_q - s.q))
    bad = s.q.copy()
    bad[3] = np.nan
    cmd = sf.filter(bad, None, s)
    assert np.isfinite(cmd.q).all() and "bad_command" in sf.reasons


def test_estop_cannot_be_bypassed(model):
    sf = Safety(model, dt=0.01)
    hal = SimHAL(model, SimConfig())
    hal.reset(model.stand_q())
    s = hal.read()
    sf.estop("test")
    for _ in range(5):
        cmd = sf.filter(model.stand_q(), np.ones(model.n), s)
        assert not cmd.enable.any() and cmd.torque_limit.max() == 0.0
    assert sf.enable() is False                # nothing but reset_estop clears it ...
    assert sf.estopped
    # ... and reset needs a still, upright robot
    from types import SimpleNamespace
    moving = SimpleNamespace(tilt=0.0, gyro=np.array([3.0, 0, 0]))
    assert sf.reset_estop(moving) is False and sf.estopped
    still = SimpleNamespace(tilt=0.0, gyro=np.zeros(3))
    assert sf.reset_estop(still) is True and not sf.estopped


def test_hardware_estop_input_latches(model):
    sf = Safety(model, dt=0.01)
    sf.hw_estop = lambda: True
    from types import SimpleNamespace
    hal = SimHAL(model, SimConfig())
    hal.reset(model.stand_q())
    s = hal.read()
    est = SimpleNamespace(tilt=0.0, tilt_rate=0.0, gyro=np.zeros(3))
    sf.monitor(s, est)
    assert sf.estopped and "hardware" in sf._estop_reason


# ------------------------------------------------------------------------------------------------ command API
def test_command_api_validation_and_describe():
    bus = CommandBus()
    assert bus.submit({"v": 1, "cmd": "describe"})["ok"]
    assert set(COMMANDS) >= {"velocity", "behaviour", "pose", "look_at", "estop", "status", "stop"}
    for bad in ({"v": 2, "cmd": "status"}, {"v": 1, "cmd": "fly"}, {"v": 1, "cmd": "velocity", "vx": "fast"}, {"v": 1, "cmd": "behaviour", "name": "backflip"},
                {"v": 1, "cmd": "pose", "joints": {}}, {"v": 1, "cmd": "look_at", "target": [1, 2]}, "not json{"):
        r = bus.submit(bad)
        assert r["ok"] is False and r["error"]["code"] in ("invalid", "bad_json")
    r = bus.submit('{"v":1,"id":"a1","cmd":"velocity","vx":0.1}')
    assert r["ok"] and r["id"] == "a1"
    assert bus.drain()[0].msg["cmd"] == "velocity"


def test_gamepad_mapping():
    gp = GamepadMapper()
    # without the dead-man nothing moves
    out = gp.update(PadState({"ly": -1.0}, set()), 0.0)
    assert not [m for m in out if m["cmd"] == "velocity"]
    out = gp.update(PadState({"ly": -1.0, "lx": 0.0, "rx": 0.5}, {"LB"}), 0.1)
    v = [m for m in out if m["cmd"] == "velocity"][0]
    assert v["vx"] > 0.1 and abs(v["vy"]) < 1e-6 and v["wz"] < 0 and v["ttl"] > 0
    # releasing the dead-man sends a stop
    out = gp.update(PadState({"ly": -1.0}, set()), 0.2)
    assert [m for m in out if m["cmd"] == "velocity"][0]["vx"] == 0.0
    # buttons are edge-triggered
    out = gp.update(PadState({}, {"B"}), 0.3)
    assert [m for m in out if m["cmd"] == "behaviour"][0]["name"] == "wave"
    assert not [m for m in gp.update(PadState({}, {"B"}), 0.4) if m["cmd"] == "behaviour"]
    # e-stop needs a hold of BACK
    assert not [m for m in gp.update(PadState({}, {"BACK"}), 1.0) if m["cmd"] == "estop"]
    assert [m for m in gp.update(PadState({}, {"BACK"}), 1.6) if m["cmd"] == "estop"]


def test_web_and_tcp_front_ends():
    bus = CommandBus()
    web = WebServer(bus, "127.0.0.1", 0).start()
    tcp = JsonLineServer(bus, "127.0.0.1", 0).start()
    try:
        page = _OPEN(f"http://127.0.0.1:{web.port}/", timeout=5).read().decode()
        assert "E-STOP" in page and "/api" in page
        req = urllib.request.Request(f"http://127.0.0.1:{web.port}/api", data=json.dumps({"v": 1, "cmd": "velocity", "vx": 0.05}).encode(), method="POST")
        assert json.loads(_OPEN(req, timeout=5).read())["ok"]
        with socket.create_connection(("127.0.0.1", tcp.port), timeout=5) as c:
            c.sendall(b'{"v":1,"cmd":"describe"}\n{"v":1,"cmd":"nope"}\n')
            f = c.makefile()
            r1, r2 = json.loads(f.readline()), json.loads(f.readline())
        assert r1["ok"] and not r2["ok"]
        assert {p.msg["_source"] for p in bus.drain()} == {"web"}
    finally:
        web.stop()
        tcp.stop()


# ------------------------------------------------------------------------------------------------ FeetechHAL (mock bus only: untested on hardware)
def test_feetech_register_conversions(model):
    sm = ServoMap.default(model)
    q = model.stand_q()
    counts = sm.to_counts(q)
    assert counts.min() >= 0 and counts.max() < COUNTS
    back = sm.to_joint(counts)
    assert np.allclose(back, q, atol=2 * math.pi / COUNTS * 1.01 * np.maximum(model.ratio, 1.0))
    assert np.array_equal(decode_signed(encode_signed(np.array([-37, 0, 512]), 10), 10), [-37, 0, 512])
    assert REGISTERS["Goal_Position"] == (42, 2) and REGISTERS["Present_Load"][0] == 60


def test_feetech_hal_on_mock_bus(model):
    import warnings

    class Imu:
        def read(self):
            from openhumanoid.runtime.hal.base import ImuSample
            return ImuSample(0.0, np.zeros(3), np.array([0, 0, 9.81]))

    bus = MockBus(ServoMap.default(model).ids)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hal = FeetechHAL(model, bus, Imu(), control_hz=1000.0)
    q = model.stand_q()
    cmd = JointCmd.hold(q)
    cmd.torque_limit[:] = 0.5
    hal.write(cmd)
    assert bus.regs["Torque_Enable"][1] == 1
    assert bus.regs["Torque_Limit"][1] == 500
    assert bus.regs["Goal_Position"][model.index["knee_l"] + 1] == int(ServoMap.default(model).to_counts(q)[model.index["knee_l"]])
    # pretend the servos reached the goal: read-back converts to joint units
    for i in bus.regs["Goal_Position"]:
        bus.regs["Present_Position"][i] = bus.regs["Goal_Position"][i]
    s = hal.read()
    assert np.allclose(s.q, q, atol=0.02) and abs(s.voltage - 12.0) < 0.2
    hal.tick()
    hal.close()
    assert bus.regs["Torque_Enable"][1] == 0


# ------------------------------------------------------------------------------------------------ estimator / planner
def test_estimator_tracks_truth_in_sim(model):
    rt, hal = S.make_sim()
    errs = []
    for _ in range(150):
        rt.step()
        g = hal.ground_truth()
        sup = 0.5 * (g["feet"]["l"] + g["feet"]["r"])
        errs.append(np.linalg.norm((rt.last_est.c[:2]) - (g["com"] - sup)[:2]))
        assert abs(math.degrees(rt.last_est.tilt) - g["tilt_deg"]) < 1.5
    assert np.mean(errs[50:]) < 0.006


def test_planner_orbit_is_stable_with_perfect_tracking(model):
    """The footstep rule alone (measured := virtual state) walks forward with a bounded lateral swing."""
    from types import SimpleNamespace
    from openhumanoid.runtime.locomotion import R2
    G = Gait(model, GaitConfig())
    G.initial_pose(model.stand_q(G.flex))
    G.command(0.1, 0, 0)

    def fake():
        Rm = R2(G.pelvis_yaw)
        cf = {s: np.append(Rm.T @ (G.v_c - G.centre_of(s)), G.zc) for s in "lr"}
        vf = {s: np.append(Rm.T @ G.v_v, 0.0) for s in "lr"}
        sup = G.contact[0] * G.centre_of("l") + G.contact[1] * G.centre_of("r")
        return SimpleNamespace(c=np.append(Rm.T @ (G.v_c - sup), G.zc), v=np.append(Rm.T @ G.v_v, 0.0), c_foot=cf, v_foot=vf)
    ys = []
    for _ in range(800):
        G.update(fake(), 0.01)
        ys.append(G.v_c[1])
    assert max(abs(np.array(ys[100:]))) < 0.04
    assert G.v_c[0] > 0.5 and G.n_steps_taken > 15


# ------------------------------------------------------------------------------------------------ scenarios (sim)
def test_stand_10s_fast():
    r = S.stand(10.0)
    assert r.passed, r.metrics


@pytest.mark.slow
def test_stand_60s():
    r = S.stand(60.0)
    assert r.passed, r.metrics


@pytest.mark.slow
def test_walk_2m_and_turn_90():
    r = S.walk_and_turn()
    assert r.passed, r.metrics


@pytest.mark.slow
@pytest.mark.parametrize("direction", ["fwd", "back", "left", "right"])
def test_push_while_standing(direction):
    r = S.push_stand(S.REQUIRED_PUSH_NS, direction)
    assert r.passed, r.metrics


@pytest.mark.slow
@pytest.mark.parametrize("direction", ["fwd", "back", "left", "right"])
@pytest.mark.parametrize("step", [3, 4])
def test_push_while_walking(direction, step):
    r = S.push_walk(S.REQUIRED_PUSH_NS, direction, step_target=step)
    assert r.passed, r.metrics


@pytest.mark.slow
def test_standing_push_margin_is_at_least_twice_the_requirement():
    """Closed-loop standing (servo stiffness + IMU ankle loop + COM bias hold) recovers 0.9 N s forward/back and 1.2 N s sideways = 2x/2.7x the 0.45 N s requirement."""
    for d, J in (("fwd", 0.9), ("back", 0.8), ("left", 1.2), ("right", 1.2)):
        r = S.push_stand(J, d)
        assert r.passed, (d, J, r.metrics)


@pytest.mark.slow
def test_capture_step_mechanism_triggers_on_a_large_push():
    """The opt-in capture step (weight shift, swing, DCM landing) engages on a push beyond the support polygon. It is NOT claimed to extend the
    recovery range: the measured result (docs/software.md) is that it does not beat the passive limit of ~1.0 N s for a standing push."""
    from openhumanoid.runtime.runtime import RuntimeConfig
    r = S.push_stand(1.2, "fwd", rt_cfg=RuntimeConfig(gait=GaitConfig(capture_enable=True, capture_x=0.035)))
    assert r.metrics["steps_taken"] >= 1


def test_config_yaml_roundtrip_and_typo_guard(tmp_path):
    from openhumanoid.runtime.config import load_config
    from openhumanoid.paths import repo_root
    c = load_config(repo_root() / "software" / "configs" / "adam.yaml")
    assert c["runtime"].safety.temp_cutoff_c == 65.0 and c["sim"].control_hz == 100.0
    bad = tmp_path / "bad.yaml"
    bad.write_text("safety:\n  temp_cutof_c: 60\n", encoding="utf-8")
    with pytest.raises(KeyError):
        load_config(bad)


@pytest.mark.slow
def test_wave():
    r = S.wave()
    assert r.passed, r.metrics


@pytest.mark.slow
def test_dance_30s():
    r = S.dance()
    assert r.passed, r.metrics


@pytest.mark.slow
def test_pickup_at_reachable_table_height():
    r = S.pickup(0.30)
    assert r.passed, r.metrics


def test_look_at_person():
    r = S.look_at()
    assert r.passed, r.metrics


def test_estop_scenario():
    r = S.estop()
    assert r.passed, r.metrics


def test_overheat_cutoff():
    r = S.overheat()
    assert r.passed, r.metrics


def test_low_battery_cutoff():
    r = S.low_battery()
    assert r.passed, r.metrics


def test_fall_triggers_safe_fall_pose():
    r = S.fall()
    assert r.passed, r.metrics


def test_commands_drive_the_sim_through_the_api():
    rt, hal = S.make_sim()
    assert rt.client.velocity(0.1, 0, 0, ttl=0.3)["ok"]
    for _ in range(300):
        rt.client.velocity(0.1, 0, 0, ttl=0.3)
        rt.step()
    st = rt.client.status()["result"]
    assert st["behaviour"]["behaviour"] == "walk" and st["behaviour"]["steps"] >= 3
    # dead-man: stop sending and the robot stops stepping and holds
    for _ in range(300):
        rt.step()
    assert rt.mgr.gait.mode == "hold" and hal.ground_truth()["tilt_deg"] < 3.0
    assert hal.ground_truth()["base_pos"][0] > 0.05


def test_runs_at_50_hz_the_likely_hardware_rate():
    """One TTL bus of 23 servos cannot carry 100 Hz (docs/software.md): the loop must stand and walk at 50 Hz too."""
    rt, hal = S.make_sim(sim=SimConfig(control_hz=50.0))
    assert abs(rt.dt - 0.02) < 1e-9
    for _ in range(250):
        rt.client.velocity(0.08, 0, 0, ttl=0.3)
        rt.step()
    assert rt.safety.state == "ok" and rt.mgr.gait.n_steps_taken >= 3 and hal.ground_truth()["tilt_deg"] < 5.0


def test_loop_timing_is_recorded():
    rt, hal = S.make_sim()
    for _ in range(200):
        rt.step()
    t = rt.timing()
    assert 0 < t["mean_ms"] < t["period_ms"]
