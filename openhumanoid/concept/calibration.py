"""Known-robot calibration against Open Duck Mini (challenge-2 rows 1 and 11).

READ-ONLY USE OF UNLICENSED DATA. Open Duck Mini's Playground and reference-motion-generator repositories carry NO LICENSE. This
module therefore reads the files the caller points it at (`odm_dir`, a scratch folder OUTSIDE the repository) at run time, keeps
nothing, and writes only DERIVED NUMBERS (gate values, ratios, masses) with their citations into the report. No ODM file, mesh, table,
coefficient or code is copied into the repository, and none is committed. The reference-motion decoder below is written from the
format that the repository's own `scripts/fit_poly.py` documents in its output (a pickle of per-command polynomial coefficients);
the pickle is inspected for unsafe opcodes before it is loaded.

Three experiments through the IDENTICAL demand + gate code (`envelopes.ideal_demand`, `joint_metrics`, `gate_joint_table`):

  (a) ODM's own MJCF with ODM's own reference motion (the 15-degree-polynomial gait that its RL policy imitates);
  (b) the FROZEN gait (thresholds.yaml `motions.walk`, and the gait-sweep set) on ODM's MJCF, with numerical leg IK;
  (c) the frozen gait on a concept spec with ODM's real leg lengths, mass and 5-DOF legs, built by our own generator.

(a) -> (b) isolates the GAIT (0.54 s ODM cycle at about 0.15 m/s on a crouched 77 deg knee, versus the frozen 0.10 m/s at 0.5 s steps),
(b) -> (c) isolates our MODEL OF THE ROBOT (mass distribution, inertias, geometry offsets, armature), and the gap between the gates and
a robot that really walks is the number the commander needs for an ADR. No gate threshold is changed here.
"""
from __future__ import annotations

import copy
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..actuators import servo_spec
from . import config, envelopes as E
from .kin import LegGeom, Reference, RobotKin, quat_from_yaw_pitch
from .playback import PlayConfig

G = 9.81
ODM_SERVO = "sts3215-7v4"                    # ODM: 14x Feetech STS3215 on a 2S pack (research/robots/benchmarks.md)
CANON = {"left_hip_yaw": "hip_yaw_l", "left_hip_roll": "hip_roll_l", "left_hip_pitch": "hip_pitch_l", "left_knee": "knee_l", "left_ankle": "ankle_pitch_l",
         "right_hip_yaw": "hip_yaw_r", "right_hip_roll": "hip_roll_r", "right_hip_pitch": "hip_pitch_r", "right_knee": "knee_r", "right_ankle": "ankle_pitch_r"}
LEG_BASES = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch"]
ODM_SCENE = Path("playground") / "open_duck_mini_v2" / "xmls" / "scene_flat_terrain.xml"
ODM_POLY = Path("playground") / "open_duck_mini_v2" / "data" / "polynomial_coefficients.pkl"


_NUMPY_NAMES = {"dtype", "scalar", "ndarray", "_reconstruct", "_frombuffer"}


class _NumpyOnly(pickle.Unpickler):
    """Unpickler that builds numpy arrays, dtypes and scalars and refuses everything else (no os.system, no arbitrary callables)."""

    def find_class(self, module, name):
        if module.split(".")[0] == "numpy" and name in _NUMPY_NAMES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name}")


def safe_load(path):
    with open(path, "rb") as f:
        return _NumpyOnly(f).load()


def pickle_is_numpy_only(path: Path) -> tuple[bool, set]:
    """True when the pickle loads with numpy classes only (the check an untrusted downloaded pickle must pass before it is used)."""
    try:
        safe_load(path)
        return True, set()
    except pickle.UnpicklingError as e:
        return False, {str(e)}


# ------------------------------------------------------------------------------------------------ the ODM model as a Robot
@dataclass
class ExternalRobot:
    """Duck-types `robot.Robot` for the pieces the playback, kinematics and gate code touch."""
    concept: dict
    spec: dict
    height: float
    joints: list
    acts: dict
    servo: dict
    names: list
    ratio: np.ndarray
    eff: np.ndarray
    geom: dict
    total_mass: float
    model: object
    transmissions: dict = field(default_factory=dict)
    mass_breakdown: dict = field(default_factory=dict)
    power_parts: dict = field(default_factory=dict)
    body: object = None
    facts: dict = field(default_factory=dict)

    def build_model(self, extra_world_xml: str = "", joint_params: dict | None = None):
        return copy.copy(self.model)

    def trans_ratio(self, name: str) -> float:
        return 1.0

    def has(self, *bases) -> bool:
        return all(b in {j["base"] for j in self.joints} for b in bases)


def load_odm(odm_dir, stance_knee_flex_deg: float = 77.0, armature: float | None = None, relax_ranges: bool = False) -> ExternalRobot:
    """Open Duck Mini's own MJCF, converted in memory (never written): canonical joint names, torque-source motors in place of the
    position actuators, no joint damping or friction (the demand code adds the BAM friction, like for every candidate), our solver
    options. Everything physical (masses, inertias, geometry, armature 0.027, ranges) is ODM's."""
    import mujoco
    root = Path(odm_dir)
    spec = mujoco.MjSpec.from_file(str(root / ODM_SCENE))
    ren = {}
    for j in spec.joints:
        if j.name in CANON:
            ren[j.name] = CANON[j.name]
    for old, new in ren.items():
        spec.joint(old).name = new
    for b in spec.bodies:
        if b.name == "base":
            b.name = "pelvis"
    for a in list(spec.actuators):
        spec.delete(a)
    sts = servo_spec(ODM_SERVO)
    lim = 2.0 * 1.05 * float(sts.stall_nm_ref)
    jn = []
    for j in spec.joints:
        if j.type == mujoco.mjtJoint.mjJNT_FREE:
            continue
        j.damping = [0.0, 0.0, 0.0]
        j.frictionloss = 0.0
        if relax_ranges:                  # ODM's own reference swings the knee to ~115 deg, past the +-90 deg range of its MJCF: let the replay follow it
            j.range = [-2.6, 2.6]
        if armature is not None:
            j.armature = [float(armature), 0.0, 0.0]
        spec.add_actuator(name=j.name, target=j.name, trntype=mujoco.mjtTrn.mjTRN_JOINT, gear=[1, 0, 0, 0, 0, 0],
                          ctrllimited=1, ctrlrange=[-lim, lim])
        jn.append(j.name)
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.iterations = 100
    spec.option.ls_iterations = 50
    spec.option.timestep = 0.002
    spec.option.disableflags = 0
    model = spec.compile()
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    # joints, ranges (deg), servos
    joints = []
    mj0 = mujoco.MjModel.from_xml_path(str(root / ODM_SCENE))
    for n in jn:
        old = next((k for k, v in CANON.items() if v == n), n)
        lo, hi = np.degrees(mj0.jnt_range[mj0.joint(old).id])
        base = n.rsplit("_", 1)[0] if n.endswith(("_l", "_r")) else n
        joints.append({"name": n, "base": base, "range": [float(lo), float(hi)], "side": n[-1] if n.endswith(("_l", "_r")) else None, "limb": "leg" if n.endswith(("_l", "_r")) else "head"})
    names = [j["name"] for j in joints]
    facts = _measure_geometry(model, mujoco)
    geom = {"thigh": facts["L1"], "shank": facts["L2"], "hip_width": 2 * facts["foot_y_plan"], "pelvis": 0.0, "ankle_height": facts["ankle_h"], "foot_length": facts["foot_len"],
            "foot_width": facts["foot_w"], "torso": 0.1, "neck": 0.02, "head": 0.1, "upper_arm": 0.0, "forearm": 0.0, "shoulder_width": 0.1}
    robot = ExternalRobot(
        concept={"id": "open-duck-mini-own", "base": "adam", "power": {"pack": "lipo-2s-2200-turnigy", "regulator": "buck-5v-5a"}}, spec={"locomotion": {"walk": {"stance_knee_flex_deg": stance_knee_flex_deg}}, "id": "odm"},
        height=0.42, joints=joints, acts={n: ODM_SERVO for n in names}, servo={n: sts for n in names}, names=names, ratio=np.ones(len(names)), eff=np.ones(len(names)),
        geom=geom, total_mass=float(model.body_mass.sum()), model=model, facts=facts)
    return robot


def _measure_geometry(model, mujoco) -> dict:
    """Leg lengths, ankle height, foot size and offsets of ODM's real MJCF, measured at its own home keyframe."""
    d = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, d, 0)
    mujoco.mj_forward(model, d)
    out = {}
    # segment lengths from the zero pose (joint anchors)
    d0 = mujoco.MjData(model)
    mujoco.mj_forward(model, d0)
    hp, kn, an = (d0.xanchor[model.joint(n).id].copy() for n in ("hip_pitch_l", "knee_l", "ankle_pitch_l"))
    out["L1"], out["L2"] = float(np.linalg.norm(kn - hp)), float(np.linalg.norm(an - kn))
    out["hip_pitch_offset_xy"] = [float(hp[0]), float(hp[1])]
    # foot: collision mesh -> sole plane, size, offset of the centre forward of the ankle axis (in the foot's flat frame)
    gid = model.geom("left_foot_bottom_tpu").id
    mid = model.geom_dataid[gid]
    v = model.mesh_vert[model.mesh_vertadr[mid]:model.mesh_vertadr[mid] + model.mesh_vertnum[mid]].copy()
    Rg = d.geom_xmat[gid].reshape(3, 3)
    w = v @ Rg.T + d.geom_xpos[gid]
    c = w - w.mean(0)
    evals, evecs = np.linalg.eigh(c.T @ c)
    n = evecs[:, 0] * np.sign(evecs[2, 0] if abs(evecs[2, 0]) > 1e-6 else 1.0)       # thinnest axis = the sole normal, pointing up
    ankle = d.xanchor[model.joint("ankle_pitch_l").id]
    heading = np.array([1.0, 0.0, 0.0]) - n * n[0]                                    # forward in the sole plane
    heading /= np.linalg.norm(heading)
    lateral = np.cross(n, heading)
    rel = w - ankle
    xs, ys, zs = rel @ heading, rel @ lateral, rel @ n
    out["foot_len"], out["foot_w"] = float(xs.max() - xs.min()), float(ys.max() - ys.min())
    out["foot_off"] = float(0.5 * (xs.max() + xs.min()))
    out["ankle_h"] = float(-zs.min())
    out["foot_y"] = float(abs(d.xanchor[model.joint("ankle_pitch_l").id][1]))        # foot (ankle) lateral position in the home pose
    out["foot_y_plan"] = float(abs(0.5 * (w[:, 1].max() + w[:, 1].min())))                # lateral position of the foot CENTRE in the home pose (the plan puts the ZMP there)
    out["sole_tilt_deg_at_home"] = float(np.degrees(np.arcsin(abs(n[0]))))
    out["total_mass_kg"] = float(model.body_mass.sum())
    # centre of mass relative to the hip-pitch axis height, at home
    com = d.subtree_com[1]
    out["com_above_hip_pitch_m"] = float(com[2] - d.xanchor[model.joint("hip_pitch_l").id][2])
    out["home_knee_flex_deg"] = float(np.degrees(d.qpos[model.joint("knee_l").qposadr[0]]))
    return out


def _has_geom(model, name) -> bool:
    try:
        model.geom(name)
        return True
    except Exception:  # noqa: BLE001
        return False
