"""Rewrite the `mechanical:` block of the Feetech STS servos in catalog/actuators/ from the vendor CAD (T-20261019-f6e2).

    .venv/Scripts/python variants/adam/cad/upper/tools/vendor_mech.py

Sources (downloaded 2026-10-19, kept local and gitignored: no licence grant, see research/actuators/feetech-sts3215/vendor-cad/README.md):
  W3D  Waveshare ST3215.step (ST3215-3D.zip, https://files.waveshare.com/upload/5/59/ST3215-3D.zip), probed with build123d
  W2D  Waveshare ST3215 2D drawing (ST3215-2D.zip, drawing "SCS215" 2022-06-08)
  F15  Feetech wiki ST-3215-C018 dimension drawing (ftservo.github.io/ftservo-wiki/products/models/st-3215-c018)
  F50  Feetech wiki ST-3250-C001 dimension drawing (ftservo.github.io/ftservo-wiki/products/models/st-3250-c001)
F15 and F50 print identical case numbers (45.22/45.23 x 24.72/24.73 x 35, 29 at the axis, spline 3.4 above it, Ø6 back boss 4.1 below it,
2 x 5264 connectors on the back face): the STS3250 uses the same case, so its block reuses the STEP-derived numbers with F50 cited.

Frame convention kept from openhumanoid/cad/components/servo.py (code unchanged): origin on the output axis at the TOP OF THE CASE
ENVELOPE, +z out of the horn side, body = box z in [-H, 0]. The vendor case is stepped: the face around the output sits 2.5 mm below the
envelope top (case 29 mm thick at the axis, 32 mm over most of the body, 35 mm over two bumps). The stock horn (Ø19.2 x 2.5) sinks 0.25 mm
into that recess, so `boss_h` is a token 0.05 mm and `horn_float` is -0.30 mm: the horn underside is 0.25 mm below the envelope top and its
top 2.25 mm above it (STEP: horn disc y 7.1..9.6, envelope top y 7.35).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
W3D = "vendor CAD: Waveshare ST3215.step (ST3215-3D.zip), measured with build123d"
W2D = "vendor drawing: Waveshare ST3215-2D.zip"
F15 = "Feetech ST-3215-C018 drawing"
F50 = "Feetech ST-3250-C001 drawing"

BLOCK = """# Mechanical interface data for CAD (openhumanoid/cad/components/servo.py). Each entry: {{v, src, conf}}.
# conf: datasheet = vendor CAD/drawing | vendor = vendor listing | derived | estimate = engineering judgement (confirm with the fit gauge).
# Vendor CAD read 2026-10-19 (T-20261019-f6e2; files local only, no licence grant): {cad_note}
# Frame: origin on the output axis at the TOP OF THE CASE ENVELOPE; +z out of the horn side; +x toward the long end; y = width.
# The case is stepped (vendor CAD): 29 mm thick at the axis, 32 mm over most of the body, 35 mm over two bumps; the face around the
# output is 2.5 mm below the envelope top, and the stock horn sinks into that recess (see horn_float).
mechanical:
  body_mm:
    v: [45.22, 24.72, 35.0]          # length (x), width (y), envelope height along the axis (z)
    src: "{dw} (45.22 x 24.72 x 35); {w3d} (bbox 45.223 x 24.723; case 34.85 incl. bumps)"
    conf: datasheet
  axis_from_near_end_mm: {{v: 10.11, src: "{w2d} (10.11); {w3d} (10.11)", conf: datasheet}}
  corner_fillet_mm: {{v: 2.0, src: "{w3d}: vertical case edges R2.0", conf: datasheet}}
  output_spline:
    teeth: {{v: 25, src: "{dw} (25T)", conf: datasheet}}
    od_mm: {{v: 5.9, src: "{w3d} (spline r 2.95); servodatabase 5.9", conf: datasheet}}
    boss_d_mm: {{v: 10.0, src: "{w3d}: horn hub Ø10 inside the 2.5 mm recess around the output (there is no boss above the case)", conf: datasheet}}
    boss_h_mm: {{v: 0.05, src: "derived from {w3d}: nothing stands above the envelope top before the horn; 0.05 is a token height (the component code needs a solid)", conf: derived}}
    horn_float_mm: {{v: -0.30, src: "derived from {w3d}: horn underside 0.25 mm BELOW the envelope top (horn sits in the recess), = boss_h + float", conf: derived}}
    protrusion_mm: {{v: 0.75, src: "{w3d}: spline end 0.75 above the envelope top (3.3 above the recessed face; {dw}: 3.4)", conf: datasheet}}
    center_screw: {{v: M3, src: "{dw} ('M3X6' machine screw into the spline)", conf: datasheet}}
  horn: {{v: round_25t, src: "openhumanoid/cad/components/data/hardware.yaml#horns (stock horn, dimensions from the same vendor CAD)", conf: datasheet}}
  back_shaft:
    note: "The back is a STATIC Ø6 boss (4.1 below the 29 mm face, 0.55 below the envelope) with a Ø2.6 pilot for a PA3.0x5 self-tapping screw. The stock idler horn (Ø19.2 x 2.2, inside the envelope's back recess) spins on it. The component's rotating 'stub' therefore models the PA3 screw head + washer (static in reality, modelled with the shafts: conservative)."
    spline_od_mm: {{v: 5.5, src: "derived: PA3 pan head Ø5.5 (ISO 7049 class) on the Ø6 boss; {dw} ('PA3.0X5 self-tapping screw' on the Ø6 back boss)", conf: derived}}
    protrusion_mm: {{v: 3.0, src: "derived from {w3d}: boss 0.55 (modelled 1.0) + screw head 2.0 below the envelope bottom", conf: derived}}
    boss_d_mm: {{v: 6.0, src: "{dw} (Ø6 back boss); {w3d} (r 3.0)", conf: datasheet}}
  case_holes:
    note: "The vendor CAD has NO holes in the long side faces. The real mounting holes are M2 holes in the top and bottom faces (face_holes). This key is kept because the component code reads it: x = the face-hole x positions, z = -0.5 (just under the top face), so interfaces.yaml lists them at the top edge. Design with face_holes, never with these."
    thread: {{v: M2, src: "{dw} ('4-M2.0'); {w3d} (Ø1.6 pilots)", conf: datasheet}}
    depth_mm: {{v: 2.8, src: "{w3d}: bottom-face holes 2.8 deep, top-face holes 1.4 deep", conf: datasheet}}
    x_mm: {{v: [8.3, 29.0], src: "{w3d}: top-face holes at x = 8.3 and 29.0 from the axis", conf: datasheet}}
    z_mm: {{v: [-0.5], src: "convention only (see note)", conf: derived}}
  face_holes:
    note: "M2 pilot holes (Ø1.6) in the case faces, x from the axis toward the long end, y across. Top = horn side. The Feetech drawings dimension a 12.5 mm pitch near the axis that does not match the Waveshare STEP; calipers decide before relying on them."
    top: {{v: [[8.3, 10.25], [8.3, -10.25], [29.0, 10.25], [29.0, -10.25]], src: "{w3d} (r 0.8, 1.4 deep)", conf: datasheet}}
    bottom: {{v: [[8.3, 10.25], [8.3, -10.25], [32.75, 10.25], [32.75, -10.25]], src: "{w3d} (r 0.8, 2.8 deep, r 1.0 counterbore)", conf: datasheet}}
    case_screws: {{v: [[-7.1, 9.35], [-7.1, -9.35], [32.75, 10.0], [32.75, -10.0]], src: "{w3d}: 8 x PA2.0 self-tapping case screws, 4 per face ({dw}: '8-PA2.0')", conf: datasheet}}
  cable:
    connector: {{v: "5264/2.54 3-pin x2 (daisy chain)", src: "{dw} ('5264/2.54 3P'); https://www.waveshare.com/wiki/ST3215_Servo", conf: datasheet}}
    face: {{v: "-z back face (plugs insert along the axis, from the back)", src: "{dw}: both sockets drawn on the back face, starting 12.5 from the axis toward the long end", conf: datasheet}}
    back_face_x_mm: {{v: [12.5, 22.0], src: "{dw}: 12.5 from the axis to the sockets; 2 sockets side by side across the width (~20.5 span); far edge estimated", conf: estimate}}
    z_mm: {{v: -30.0, src: "convention for the component code's end-face keep-out (code unchanged): plug room is reserved at the far end as well; the real plugs need room BELOW the back face (back_plug_room_mm)", conf: derived}}
    socket_wh_mm: {{v: [12.0, 8.0], src: "estimate (5264 3-pin housing ~7.5 x 4.9 per socket, two sockets)", conf: estimate}}
    plug_len_mm: {{v: 14.0, src: "estimate: plug + bend radius room", conf: estimate}}
    back_plug_room_mm: {{v: 12.0, src: "estimate: 5264 plug ~7 mm + 5 mm bend of 26 AWG leads below the back face", conf: estimate}}
"""


def block(servo: str) -> str:
    dw = F50 if servo == "sts3250-12v" else F15
    cad = ("Waveshare ST3215 STEP + 2D drawing (same case per the Feetech ST-3250-C001 drawing, which matches F15 number for number)"
           if servo == "sts3250-12v" else "Waveshare ST3215 STEP + 2D drawing, Feetech ST-3215-C018 drawing")
    if servo == "sts3215-7v4":
        cad += "; the 7.4 V C001 shares the case (Feetech wiki lists the same 45.22 x 24.72 x 35 body; not re-measured)"
    return BLOCK.format(cad_note=cad, dw=dw, w3d=W3D, w2d=W2D)


def main() -> None:
    for sid in ("sts3215-12v", "sts3215-7v4", "sts3250-12v"):
        p = ROOT / "catalog" / "actuators" / f"{sid}.yaml"
        lines = p.read_text(encoding="utf-8").splitlines()
        i = next(k for k, ln in enumerate(lines) if ln.startswith("# Mechanical interface data"))
        p.write_text("\n".join(lines[:i]) + "\n" + block(sid), encoding="utf-8")
        print("rewrote", p)


if __name__ == "__main__":
    main()
