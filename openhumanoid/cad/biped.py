"""`biped_v1` CAD template: spec + sizing -> frame + shell assembly as a link tree (build123d).

Variant-agnostic. Everything comes from the spec (proportions, joints, height, bed), from sizing
(height, selected actuators) and from the catalog (servo dimensions/masses). Look-and-feel knobs live
in an optional `<variant>/cad/style.yaml` merged over STYLE below.

Scope: box-type servos (bus servos: STS/SCS, Dynamixel X/AX, ...) at every joint. Each joint is a servo
whose horn drives a U-yoke. Compound joints (hip yaw/roll/pitch, ankle pitch/roll) are gimbals with
intersecting axes, so the CAD matches the sim's coincident joints exactly. Cylindrical actuators (BLDC)
need another template.
"""
from __future__ import annotations

import copy
import math
import re
from pathlib import Path

import build123d as bd
import yaml

from .. import catalog
from ..spec import deep_merge, expand_joints
from .geom import (Link, Part, ServoDims, Station, bbox_of, box, fit_stations, hollow_loft, loft_solid,
                   rounded_plate, servo_shapes)

BOX_SERVO_TYPES = {"serial_bus_servo", "pwm_servo", "smart_servo"}

STYLE: dict = {
    "frame_wall_mm": 2.5,      # bracket plate thickness
    "clearance_mm": 1.5,       # moving-part clearance
    "plate_radius_mm": 3.0,
    "shell_wall_mm": 1.6,
    "shell_gap_mm": 1.5,       # frame-to-shell gap
    "section_exponent": 2.6,   # superellipse sections: 2 = ellipse, ~2.6 = soft squircle
    "sole_mm": 3.0,
    "densities_kg_m3": {"pla-plus": 1240, "petg": 1270, "tpu": 1210},
    "fill_fraction": {"frame": 0.55, "shell": 1.0, "sole": 1.0, "hand": 0.35},
    "materials": {"frame": "pla-plus", "shell": "pla-plus", "accent_shell": "pla-plus", "visor": "petg", "sole": "tpu"},
    # Relative size along each segment, t = 0 at the proximal end .. 1 at the distal end.
    "profiles": {
        "thigh": [[0, 1.0], [0.2, 1.0], [1, 0.84]],
        "shank": [[0, 0.9], [0.3, 1.0], [1, 0.74]],
        "upper_arm": [[0, 1.0], [1, 0.93]],
        "forearm": [[0, 0.97], [1, 0.82]],
        "torso": [[0, 1.0], [0.4, 1.0], [1, 0.86]],
        "pelvis": [[0, 1.0], [1, 0.96]],
        "hip": [[0, 1.0], [1, 0.95]],
        "head": [[0, 0.88], [0.25, 1.0], [0.8, 1.0], [1, 0.9]],
    },
    "colors": {   # render palette keys -> rgba
        "shell": [0.93, 0.92, 0.90, 1], "accent_shell": [0.16, 0.16, 0.18, 1], "frame": [0.22, 0.22, 0.24, 1],
        "servo": [0.06, 0.06, 0.07, 1], "visor": [0.02, 0.02, 0.03, 1], "sole": [0.05, 0.05, 0.05, 1],
        "purchased": [0.15, 0.35, 0.2, 1],
    },
    "accent_links": ["pelvis", "hip_yaw_link"],   # shells printed in the dark accent colour
    "visor": {"front_frac": 0.12, "z_frac": [0.2, 0.84]},
    "hand_frac": 0.3,           # fraction of the forearm length that is hand
    "payload": [],              # [{part, dims_mm: [x,y,z], slot: back|core}] estimates for packaging
}


def load_style(spec: dict) -> dict:
    p = Path(spec["_dir"]) / "cad" / "style.yaml"
    over = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return deep_merge(STYLE, over or {})


def mirror_part(p: Part, side_from="_l", side_to="_r") -> Part:
    q = copy.copy(p)
    q.shape = p.shape.mirror(bd.Plane.XZ)
    q.id = re.sub(rf"{side_from}(?=_|$)", side_to, p.id)
    return q


class Builder:
    def __init__(self, spec: dict, sizing: dict, style: dict | None = None):
        self.spec, self.sizing = spec, sizing
        self.style = style or load_style(spec)
        self.g = {k: v * 1000 for k, v in sizing["geometry_m"].items()}
        self.joints = expand_joints(spec, sizing["joints_base"])
        self.base = set(sizing["joints_base"])
        acts = sizing["actuators"]
        self.servo_id = {j["name"]: acts[j["name"]] for j in self.joints}
        for j in self.joints:
            a = catalog.get(acts[j["name"]])
            if a.get("actuator", {}).get("type") not in BOX_SERVO_TYPES or not a.get("dimensions_mm"):
                raise ValueError(f"biped_v1 CAD handles box servos only; {j['name']} uses {a['id']} "
                                 f"({a.get('actuator', {}).get('type')}). Add a template for this actuator class.")
        # One envelope per joint base (uniform designs share one; mixed designs are handled per joint).
        self.sd = {j["base"]: ServoDims.from_catalog(catalog.get(acts[j["name"]])) for j in self.joints}
        st = self.style
        self.t, self.c = st["frame_wall_mm"], st["clearance_mm"]
        self.margin = st["shell_gap_mm"] + st["shell_wall_mm"]
        self.n = st["section_exponent"]
        self.links: dict[str, Link] = {}
        self.notes: list[str] = []

    # ------------------------------------------------------------------ helpers
    def S(self, base: str) -> ServoDims:
        return self.sd.get(base) or next(iter(self.sd.values()))

    def plate(self, xr, yr, zr) -> bd.Shape:
        return rounded_plate(xr, yr, zr, self.style["plate_radius_mm"])

    def frame(self, pid, shape, link) -> Part:
        return Part(pid, shape, "frame", self.style["materials"]["frame"], "frame",
                    print={"supports": False, "infill_pct": 30, "walls": 4})

    def servo(self, pid, base, jname, origin, axis, length_dir) -> list[Part]:
        s = self.S(base)
        body, horn = servo_shapes(s, origin, axis, length_dir)
        cid = self.servo_id.get(jname) or next(iter(self.servo_id.values()))
        mass = catalog.get(cid).get("mass_kg", 0.0)
        return [Part(pid, body, "servo", "purchased", "servo", mass_kg=mass, catalog=cid),
                Part(pid + "_horn", horn, "horn", "purchased", "servo", mass_kg=0.0, fit=False)]

    def shell(self, pid, parts, z_top, z_bot, profile, color="shell", n=None, **kw) -> Part:
        n = n or self.n
        st = fit_stations([p.shape for p in parts if p.fit], z_top, z_bot, profile, self.margin, n, **kw)
        shape = hollow_loft(st, self.style["shell_wall_mm"], n)
        mat = self.style["materials"]["accent_shell" if color == "accent_shell" else "shell"]
        return Part(pid, shape, "shell", mat, color, fit=False,
                    print={"supports": True, "infill_pct": 100, "walls": 2, "layer_mm": 0.12})

    def yoke(self, base: str, x_back: float, x_front: float, close: str | None) -> list[bd.Shape]:
        """U-yoke around a pitch-type axis (y): two side plates outside the horn + an optional closing plate
        at the back or front (where the next servo's horn attaches)."""
        s = self.S(base)
        y0, y1 = s.H / 2 + s.horn_t, s.H / 2 + s.horn_t + self.t
        r = s.horn_d / 2 + self.t
        out = [self.plate((x_back, x_front), (y0, y1), (-r, r)), self.plate((x_back, x_front), (-y1, -y0), (-r, r))]
        if close == "back":
            out.append(self.plate((x_back, x_back + self.t), (-y1, y1), (-r, r)))
        elif close == "front":
            out.append(self.plate((x_front - self.t, x_front), (-y1, y1), (-r, r)))
        return out

    def add(self, name, parent, pos, joint_bases, side, parts, rot=(0.0, 0.0, 0.0)):
        js = [dict(name=j["name"], axis=j["axis"], range=j["range"]) for b in joint_bases for j in self.joints
              if j["base"] == b and j["side"] == side]
        self.links[name] = Link(name, parent, tuple(pos), js, parts, tuple(rot))

    # ------------------------------------------------------------------ build
    def build(self) -> dict[str, Link]:
        g, t, c = self.g, self.t, self.c
        S = self.S("hip_pitch")
        yoke_r = S.horn_d / 2 + t
        rc = S.corner_r
        # Gimbal stand-offs: distance from the joint centre to the next servo's horn face.
        self.zf = max(yoke_r, rc) + c + t + S.horn_t        # hip yaw servo face above the hip centre
        self.xr = rc + c + t + S.horn_t                      # roll servo face from the gimbal centre
        a_hw = S.H / 2 + S.horn_t + t                        # half-width of a yoke (arm/leg frame)
        self.spacer = self.margin + c + self.style.get("shoulder_spacer_mm", 0.0)   # horn extension through the torso shell
        self.leg("l")
        self.arm("l")
        for name in [n for n in self.links if n.endswith("_l")]:
            L = self.links[name]
            par = L.parent[:-2] + "_r" if L.parent and L.parent.endswith("_l") else L.parent
            x, y, z = L.pos_mm
            js = [dict(name=j["name"][:-2] + "_r", axis=j["axis"],
                       range=next(k["range"] for k in self.joints if k["name"] == j["name"][:-2] + "_r")) for j in L.joints]
            rx, ry, rz = L.rot_deg
            self.links[name[:-2] + "_r"] = Link(name[:-2] + "_r", par, (x, -y, z), js, [mirror_part(p) for p in L.parts],
                                                (-rx, ry, -rz))
        self.trunk(a_hw)
        # Parents first (MJCF writer and FK need it).
        order, seen = [], set()

        def visit(n):
            if n in seen:
                return
            p = self.links[n].parent
            if p:
                visit(p)
            seen.add(n)
            order.append(n)
        for n in list(self.links):
            visit(n)
        return {n: self.links[n] for n in order}

    # ------------------------------------------------------------------ legs
    def leg(self, sd: str):
        g, t, c, st = self.g, self.t, self.c, self.style
        S = self.S("hip_pitch")
        yoke_r, rc, off, L, W, H = S.horn_d / 2 + t, S.corner_r, S.shaft_offset, S.L, S.W, S.H
        y1 = H / 2 + S.horn_t + t
        hy = g["hip_width"] / 2
        pz = -g["pelvis"] / 2
        prof = st["profiles"]

        # hip_yaw_link: carries the roll servo behind the hip centre ("glute"), hangs from the yaw horn.
        yaw_parts = []
        if "hip_roll" in self.base:
            xr = self.xr
            yaw_parts += self.servo(f"hip_roll_servo_{sd}", "hip_roll", f"hip_roll_{sd}", (-xr, 0, 0), (1, 0, 0), (0, 0, 1))
            pz0 = self.zf - S.horn_t - t
            straps = self.frame(f"hip_roll_cradle_{sd}", self.plate((-xr - H, -xr + S.horn_t - c), (W / 2, W / 2 + t), (-off, pz0 + t))
                                + self.plate((-xr - H, -xr + S.horn_t - c), (-(W / 2 + t), -W / 2), (-off, pz0 + t)), None)
            yaw_parts.append(straps)
            cap_fit = [q for q in yaw_parts if q.kind in ("servo", "frame")]
            yaw_parts.append(self.frame(f"hip_yaw_bracket_{sd}", self.plate((-xr + S.horn_t - c - 1, yoke_r + c), (-(W / 2 + t), W / 2 + t),
                                                                            (pz0, pz0 + t)), None))
            cap = self.shell(f"hip_cap_{sd}", cap_fit, L - off + t, -off, prof["hip"],
                             color="accent_shell" if "hip_yaw_link" in st["accent_links"] else "shell")
            cap.shape = cap.shape - box((-xr, 200), (-200, 200), (-500, 500))   # open front: the roll horn drives the yoke
            yaw_parts.append(cap)
        self.add(f"hip_yaw_link_{sd}", "pelvis", (0, hy, pz), ["hip_yaw"], sd, yaw_parts)

        # hip_roll_link: yoke between the roll horn (back) and the pitch horn (sides).
        roll_parts = [self.frame(f"hip_yoke_{sd}", bd.Compound(self.yoke("hip_pitch", -self.xr + S.horn_t, yoke_r, "back")).fuse(), None)]
        self.add(f"hip_roll_link_{sd}", f"hip_yaw_link_{sd}", (0, 0, 0), ["hip_roll"], sd, roll_parts)

        # thigh: hip-pitch servo at the top, knee servo at the bottom, C-channel between them.
        th = g["thigh"]
        p = []
        p += self.servo(f"hip_pitch_servo_{sd}", "hip_pitch", f"hip_pitch_{sd}", (0, H / 2, 0), (0, 1, 0), (0, 0, -1))
        p += self.servo(f"knee_servo_{sd}", "knee", f"knee_{sd}", (0, H / 2, -th), (0, 1, 0), (0, 0, 1))
        ch = self.plate((W / 2, W / 2 + t), (-H / 2, H / 2), (-th - off + 2, off - 2))
        ch = ch + self.plate((-W / 2 - t, -W / 2), (-H / 2, H / 2), (-th - off + 2, off - 2))
        p.append(self.frame(f"thigh_frame_{sd}", ch, None))
        hip_sweep = math.hypot(self.xr - S.horn_t, yoke_r)      # hip yoke corners swing around the pitch axis
        knee_sweep = math.hypot(W / 2 + t, yoke_r)               # shank yoke corners swing around the knee
        p.append(self.shell(f"thigh_shell_{sd}", p, -(hip_sweep + c), -th + knee_sweep + c, prof["thigh"]))
        self.add(f"thigh_{sd}", f"hip_roll_link_{sd}", (0, 0, 0), ["hip_pitch"], sd, p)

        # shank: yoke on the knee horn, ankle-pitch servo at the bottom.
        sh = g["shank"]
        Sa = self.S("ankle_pitch")
        xr_a = Sa.corner_r + c + t + Sa.horn_t
        ank_r = math.hypot(xr_a - Sa.horn_t, Sa.horn_d / 2 + t)     # ankle yoke sweep radius
        z_lo = -sh + ank_r + c
        p = []
        p += self.servo(f"ankle_pitch_servo_{sd}", "ankle_pitch", f"ankle_pitch_{sd}", (0, Sa.H / 2, -sh), (0, 1, 0), (0, 0, 1))
        fr = self.plate((-(W / 2 + t), W / 2 + t), (H / 2 + S.horn_t, y1), (z_lo, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), W / 2 + t), (-y1, -(H / 2 + S.horn_t)), (z_lo, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), -W / 2), (-y1, y1), (-sh + Sa.L - Sa.shaft_offset, -(rc + c)))
        p.append(self.frame(f"shank_frame_{sd}", fr, None))
        p.append(self.shell(f"shank_shell_{sd}", p, -(max(yoke_r, rc) + c), z_lo + 2, prof["shank"]))
        self.add(f"shank_{sd}", f"thigh_{sd}", (0, 0, -th), ["knee"], sd, p)

        # ankle_pitch_link: yoke around the pitch horn, closed at the front by the roll horn.
        p = [self.frame(f"ankle_yoke_{sd}", bd.Compound(self.yoke("ankle_pitch", -(Sa.horn_d / 2 + t), xr_a - Sa.horn_t, "front")).fuse(), None)]
        self.add(f"ankle_pitch_link_{sd}", f"shank_{sd}", (0, 0, -sh), ["ankle_pitch"], sd, p)

        # foot: roll servo lying in the forefoot (shaft pointing back at the ankle centre), plate, sole, shell.
        Sr = self.S("ankle_roll")
        ah, sole = g["ankle_height"], st["sole_mm"]
        p = []
        if "ankle_roll" in self.base:
            p += self.servo(f"ankle_roll_servo_{sd}", "ankle_roll", f"ankle_roll_{sd}", (xr_a, 0, 0), (-1, 0, 0), (0, 1, 0))
        fl, fw = g["foot_length"], g["foot_width"]
        x_heel = min(fl * 0.15 - fl / 2, -(Sa.horn_d / 2 + t) - 6)
        x_toe = max(fl * 0.15 + fl / 2, xr_a + Sr.H + 4)
        y_in, y_out = -max(fw / 2, Sr.shaft_offset + t), max(fw / 2, Sr.L - Sr.shaft_offset + t)
        if x_toe - x_heel > fl + 0.5 or y_out - y_in > fw + 0.5:
            self.notes.append(f"foot grows to {x_toe - x_heel:.0f} x {y_out - y_in:.0f} mm (spec {fl:.0f} x {fw:.0f}) to house the ankle-roll servo")
        z_pl = -ah + sole
        servo_bot = -Sr.W / 2
        if servo_bot - z_pl < t + 1:
            self.notes.append(f"ankle height {ah:.1f} mm leaves {servo_bot - z_pl:.1f} mm under the ankle-roll servo (< plate {t} mm)")
        fp = self.plate((x_heel + 4, x_toe - 4), (y_in + 2, y_out - 2), (z_pl, z_pl + t))
        if servo_bot > z_pl + t + 0.5 and "ankle_roll" in self.base:
            fp = fp + box((xr_a, xr_a + Sr.H), (-Sr.shaft_offset, Sr.L - Sr.shaft_offset), (z_pl + t - 0.5, servo_bot))
        p.append(self.frame(f"foot_frame_{sd}", fp, None))
        sole_shape = rounded_plate((x_heel, x_toe), (y_in, y_out), (-ah, -ah + sole), min(12.0, (y_out - y_in) * 0.45))
        p.append(Part(f"sole_{sd}", sole_shape, "sole", st["materials"]["sole"], "sole", fit=False,
                      print={"supports": False, "infill_pct": 40, "walls": 3}))
        p.append(self.foot_shell(f"foot_shell_{sd}", p, x_heel, x_toe, y_in, y_out, z_pl))
        self.add(f"foot_{sd}", f"ankle_pitch_link_{sd}", (0, 0, 0), ["ankle_roll"], sd, p)

    def foot_shell(self, pid, parts, x_heel, x_toe, y_in, y_out, z_pl) -> Part:
        """Low wedge: superellipse sections along x, flat bottom on the foot plate, tallest over the roll servo."""
        st = self.style
        sv = [bbox_of(p.shape) for p in parts if p.kind == "servo"]
        if not sv:
            return Part(pid, box((x_heel, x_toe), (y_in, y_out), (z_pl, z_pl + 1)), "shell", st["materials"]["shell"], "shell", fit=False)
        (sx0, sx1), (sy0, sy1), (_, sz1) = sv[0]
        top = sz1 + self.margin
        z_pl = z_pl + self.t                                 # sits on the foot plate
        x0 = sx0 - 0.5                                       # open back: the roll horn passes through
        cy = (y_in + y_out) / 2
        hw = max((y_out - y_in) / 2, (sy1 - sy0) / 2 + self.margin)
        h = (top - z_pl) * 1.3                               # taller sections, bottom cut flat below
        hw = max(hw, (sy1 - sy0) / 2 * 1.26 + self.margin)
        secs = []
        x_end = max(x_toe, sx1 + self.margin + 6)
        for x, kh, kw in [(x0, 1.0, 1.0), (x0 + 0.5 * (sx1 - x0), 1.04, 1.0), (sx1 + self.margin, 1.0, 1.0),
                          (x_end - 2.5, 0.7, 0.9), (x_end, 0.4, 0.7)]:
            # local frame: x -> world z (height), y -> world -y, z -> world x (along the foot)
            hk = h * kh
            secs.append(Station(x, hk / 2, hw * kw, top + self.margin * 0.3 - hk / 2, -cy))
        sol = hollow_loft(secs, st["shell_wall_mm"], self.n, open_ends="lo")
        shape = bd.Location(bd.Plane(origin=(0, 0, 0), x_dir=(0, 0, 1), z_dir=(1, 0, 0))) * sol
        shape = shape & box((x0 - 5, x_end + 5), (cy - 3 * hw, cy + 3 * hw), (z_pl + 0.2, top + 50))
        return Part(pid, shape, "shell", st["materials"]["shell"], "shell", fit=False,
                    print={"supports": True, "infill_pct": 100, "walls": 2, "layer_mm": 0.12})

    # ------------------------------------------------------------------ arms
    def arm(self, sd: str):
        if "shoulder_pitch" not in self.base:
            return
        g, t, c, st = self.g, self.t, self.c, self.style
        S = self.S("elbow")
        yoke_r, rc, off, W, H = S.horn_d / 2 + t, S.corner_r, S.shaft_offset, S.W, S.H
        a_hw = H / 2 + S.horn_t + t
        ua, fa = g["upper_arm"], g["forearm"]
        prof = st["profiles"]
        ank_r = math.hypot(W / 2 + t, yoke_r)
        z_lo = -ua + ank_r + c
        p = []
        if "elbow" in self.base:
            p += self.servo(f"elbow_servo_{sd}", "elbow", f"elbow_{sd}", (0, H / 2, -ua), (0, 1, 0), (0, 0, 1))
        fr = self.plate((-(W / 2 + t), W / 2 + t), (a_hw - t, a_hw), (z_lo, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), W / 2 + t), (-a_hw, -a_hw + t), (z_lo, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), W / 2 + t), (-a_hw, a_hw), (yoke_r - t, yoke_r))
        p.append(self.frame(f"upper_arm_frame_{sd}", fr, None))
        spacer = self.frame(f"shoulder_spacer_{sd}", bd.Pos(0, -a_hw - self.spacer / 2, 0) * bd.Rot(90, 0, 0)
                            * bd.Cylinder(S.horn_d / 2, self.spacer), None)
        ush = self.shell(f"upper_arm_shell_{sd}", p, yoke_r + c, z_lo + 2, prof["upper_arm"])
        ush.shape = ush.shape - box((-200, 200), (-200, -(a_hw + 0.5)), (-500, 500))  # flat inner face next to the torso
        p.append(ush)
        # optional fixed outward cant below the shoulder horn (A-pose) so the hands clear the hips
        cant = st.get("arm_cant_deg", 0.0)
        if cant:
            spin = bd.Rot(cant, 0, 0)
            for q in p:
                q.shape = spin * q.shape
        p.append(spacer)
        self.add(f"upper_arm_{sd}", "torso", (0, g["shoulder_width"] / 2, g["torso"] * 0.9), ["shoulder_pitch", "shoulder_roll"], sd, p)

        hand_len = fa * st["hand_frac"]
        z_sp = -(fa - hand_len) + 4
        p = []
        z_y = -(yoke_r + c + 2 * t)          # yoke bottom; a slim spar runs on to the wrist
        fr = self.plate((-(W / 2 + t), W / 2 + t), (a_hw - t, a_hw), (z_y, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), W / 2 + t), (-a_hw, -a_hw + t), (z_y, yoke_r))
        fr = fr + self.plate((-(W / 2 + t), W / 2 + t), (-a_hw, a_hw), (z_y - t, z_y))
        fr = fr + self.plate((-W / 2, W / 2), (-2 * t, 2 * t), (z_sp - t, z_y))
        p.append(self.frame(f"forearm_frame_{sd}", fr, None))
        p.append(self.shell(f"forearm_shell_{sd}", p, z_y - t - c, z_sp - t, prof["forearm"],
                            min_half=((W / 2 + t) * 0.8, a_hw * 0.8)))
        hz0, hz1 = -(fa - hand_len) - 2, -fa
        hand = loft_solid([Station(hz0, W / 2, a_hw * 0.8), Station((hz0 + hz1) / 2, W / 2 * 0.95, a_hw * 0.85),
                           Station(hz1 + 4, W / 2 * 0.7, a_hw * 0.6), Station(hz1, W / 2 * 0.35, a_hw * 0.3)], self.n)
        p.append(Part(f"hand_{sd}", hand, "hand", st["materials"]["accent_shell"], "accent_shell", fit=False,
                      print={"supports": False, "infill_pct": 20, "walls": 3}))
        for q in p:
            if q.kind == "shell":
                q.shape = q.shape - box((-200, 200), (-200, -(a_hw + 0.5)), (-500, 500))
        cant = math.radians(st.get("arm_cant_deg", 0.0))
        self.add(f"forearm_{sd}", f"upper_arm_{sd}", (0, ua * math.sin(cant), -ua * math.cos(cant)), ["elbow"], sd, p,
                 rot=(math.degrees(cant), 0, 0))

    # ------------------------------------------------------------------ pelvis, torso, head
    def trunk(self, a_hw: float):
        g, t, c, st = self.g, self.t, self.c, self.style
        S = self.S("hip_yaw")
        off, L, W, H = S.shaft_offset, S.L, S.W, S.H
        hy, pz = g["hip_width"] / 2, -g["pelvis"] / 2
        prof = st["profiles"]
        pel = []
        if "hip_yaw" in self.base:
            # yaw servos lie across the pelvis (long side pointing inwards) to keep the waist shallow
            for sd, sgn in (("l", 1), ("r", -1)):
                pel += self.servo(f"hip_yaw_servo_{sd}", "hip_yaw", f"hip_yaw_{sd}", (0, sgn * hy, pz + self.zf), (0, 0, -1), (0, -sgn, 0))
            if hy - (L - off) < 1:
                self.notes.append(f"hip yaw servos meet at the centre: hip_width {2 * hy:.0f} mm < {2 * (L - off) + 2:.0f} mm")
        z_top = pz + self.zf + H
        ys = hy + off + t
        cr = self.plate((-W / 2 - t, W / 2 + t), (-ys, ys), (z_top, z_top + t))
        cr = cr + self.plate((W / 2, W / 2 + t), (-ys, ys), (pz + self.zf + 2, z_top))
        cr = cr + self.plate((-W / 2 - t, -W / 2), (-ys, ys), (pz + self.zf + 2, z_top))
        pel.append(self.frame("pelvis_frame", cr, None))

        # torso: chest + back plates between the yaw cradle and the shoulder servos; payload behind/inside.
        to = g["torso"]
        zc = z_top + t - g["pelvis"] / 2        # cradle top in the torso frame
        Sh = self.S("shoulder_pitch")
        z_sh = to * 0.9
        y_face = g["shoulder_width"] / 2 - a_hw - self.spacer - Sh.horn_t
        p = []
        if "shoulder_pitch" in self.base:
            for sd, sgn in (("l", 1), ("r", -1)):
                p += self.servo(f"shoulder_servo_{sd}", "shoulder_pitch", f"shoulder_pitch_{sd}", (0, sgn * y_face, z_sh),
                                (0, sgn, 0), (0, 0, -1))
            if y_face - Sh.H < 1:
                self.notes.append(f"shoulder servos collide at the centre (gap {2 * (y_face - Sh.H):.1f} mm): shoulder_width too small")
        z_t = z_sh + Sh.shaft_offset
        z_sb = z_sh - (Sh.L - Sh.shaft_offset)      # shoulder servo bottoms: frame narrows below (waist)
        yw = max(y_face, W)
        yl = yw * st.get("waist_frame_frac", 0.75)
        fr = None
        for x0, x1 in ((Sh.W / 2, Sh.W / 2 + t), (-Sh.W / 2 - t, -Sh.W / 2)):
            for pl in (self.plate((x0, x1), (-yw, yw), (z_sb - 2, z_t + t)), self.plate((x0, x1), (-yl, yl), (zc, z_sb))):
                fr = pl if fr is None else fr + pl
        fr = fr + self.plate((-Sh.W / 2 - t, Sh.W / 2 + t), (-yw, yw), (z_t, z_t + t))
        p.append(self.frame("torso_frame", fr, None))
        # payload envelopes (battery, boards) from style estimates
        back_x, core_z = -Sh.W / 2 - t, zc + 2
        back_z0 = zc + 1 - st.get("back_payload_drop_mm", 0.0)
        for it in st.get("payload", []):
            dx, dy, dz = it["dims_mm"]
            part = catalog.get(it["part"])
            if "at_mm" in it:
                x, y, z = it["at_mm"]
                shp = box((x - dx / 2, x + dx / 2), (y - dy / 2, y + dy / 2), (z - dz / 2, z + dz / 2))
            elif it.get("slot") == "back":
                shp = box((back_x - dx, back_x), (-dy / 2, dy / 2), (back_z0, back_z0 + dz))
                back_x -= dx + 1
            else:
                shp = box((-dx / 2, dx / 2), (-dy / 2, dy / 2), (core_z, core_z + dz))
                core_z += dz + 1
            p.append(Part(f"payload_{it['part']}", shp, "purchased", "purchased", "purchased", mass_kg=part.get("mass_kg", 0.0),
                          catalog=it["part"]))
            if it.get("slot") != "back" and "at_mm" not in it and core_z > z_sb:
                self.notes.append(f"core payload stack reaches the shoulder servos at {it['part']}")
        top = max([z_t + t] + [bbox_of(q.shape)[2][1] for q in p if q.kind == "purchased"])
        sh = self.shell("torso_shell", p, top + self.margin, zc + c, prof["torso"])
        # pelvis band also covers torso payload that hangs below the chest shell
        lift = bd.Pos(0, 0, g["pelvis"] / 2)
        below = [Part("_fit", lift * q.shape, "purchased", "purchased") for q in p if q.kind == "purchased"
                 and bbox_of(q.shape)[2][0] < zc + c]
        band_bot = pz + self.zf - S.horn_t - c
        pel.append(self.shell("pelvis_shell", pel + below, z_top + t, band_bot, prof["pelvis"],
                              color="accent_shell" if "pelvis" in st["accent_links"] else "shell", n=max(self.n, 4.0), dome=0.45, dome_shrink=0.72))
        self.add("pelvis", None, (0, 0, 0), [], None, pel)
        hole = bd.Pos(0, 0, z_sh) * bd.Rot(90, 0, 0) * bd.Cylinder(Sh.horn_d / 2 + c, g["shoulder_width"] + 40)
        sh.shape = sh.shape - hole
        p.append(sh)
        self.add("torso", "pelvis", (0, 0, g["pelvis"] / 2), [], None, p)

        # head: neck post + pill shell with a glossy front visor.
        hd, nk = g["head"], g["neck"]
        hw = hd * 0.62
        p = []
        neck_r = max(hw * 0.22, 6)
        neck = bd.Pos(0, 0, (-(nk + to - z_t - t) + hd * 0.2) / 2) * bd.Cylinder(neck_r, nk + (to - z_t - t) + hd * 0.2)
        if "neck_yaw" in self.base:
            p += self.servo("neck_servo", "neck_yaw", "neck_yaw", (0, 0, -nk / 2), (0, 0, 1), (1, 0, 0))
        p.append(self.frame("neck_post", neck, None))
        a, b = hw * 0.62, hw / 2
        stations = []
        for tt, k in [(0.0, 0.55), (0.06, 0.85), (0.2, 1.0), (0.8, 1.0), (0.94, 0.85), (1.0, 0.5)]:
            stations.append(Station(hd * tt, a * k, b * k, 0, 0))
        outer = hollow_loft(stations, st["shell_wall_mm"], self.n, open_ends=False)
        outer = outer - bd.Pos(0, 0, 0) * bd.Cylinder(neck_r + c, 8)     # neck opening
        v = st["visor"]
        vbox = box((a * v["front_frac"], a + 5), (-b - 5, b + 5), (hd * v["z_frac"][0], hd * v["z_frac"][1]))
        visor = outer & vbox
        rest = outer - vbox
        p.append(Part("head_shell", rest, "shell", st["materials"]["shell"], "shell", fit=False,
                      print={"supports": True, "infill_pct": 100, "walls": 2, "layer_mm": 0.12}))
        p.append(Part("visor", visor, "shell", st["materials"]["visor"], "visor", fit=False,
                      print={"supports": True, "infill_pct": 100, "walls": 2, "layer_mm": 0.12, "finish": "polish"}))
        self.add("head", "torso", (0, 0, to + nk), ["neck_yaw"], None, p)


def build(spec: dict, sizing: dict, style: dict | None = None) -> tuple[dict[str, Link], list[str]]:
    b = Builder(spec, sizing, style)
    links = b.build()
    return links, b.notes
