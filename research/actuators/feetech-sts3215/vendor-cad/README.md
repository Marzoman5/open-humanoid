# STS3215 / STS3250 vendor CAD: derived dimensions (T-20261019-f6e2, 2026-10-19)

The files themselves are **not committed** (`.gitignore` here): neither Waveshare nor Feetech grants a licence for them
(THIRD_PARTY.md). Re-download them to this folder to repeat the measurement:

| File | Source | Size |
|---|---|---|
| `ST3215-3D.zip` -> `3D/ST3215.step` | https://files.waveshare.com/upload/5/59/ST3215-3D.zip (Waveshare wiki "ST3215 Servo") | 566,939 B (STEP 3,025,101 B) |
| `ST3215-2D.zip` -> `2D/ST3215.pdf`, `2D/ST3215.dxf` | https://files.waveshare.com/upload/0/08/ST3215-2D.zip (drawing "SCS215", 2022-06-08) | 172,516 B |
| `ST-3215-C018-drawing.webp` | https://ftservo.github.io/ftservo-wiki/products/models/st-3215-c018/images/drawing.webp | 271,176 B |
| `../../feetech-sts3250/vendor-cad/ST-3250-C001-drawing.webp` | https://ftservo.github.io/ftservo-wiki/products/models/st-3250-c001/images/drawing.webp | 33,916 B |

No STEP exists for the STS3250 (Feetech wiki: "STEP / 3D model: to be supplemented"; the datasheet PDF link timed out). Its drawing prints
the same case numbers as the ST-3215-C018 drawing, so the STS3250 block reuses the STEP-derived numbers.

Measured with `build123d` (`import_step`, sections through the solids, circular-edge listing). STEP frame: x along the length, y along the
output axis (+y horn side), z across; output axis at x = -25.5.

## Derived dimensions (the catalog `mechanical:` blocks and `hardware.yaml#horns` cite these)

| Feature | Before (estimate) | Vendor CAD | Change |
|---|---|---|---|
| Body L x W x H | 45.2 x 24.7 x 35.0 (vendor listing) | 45.22 x 24.72 x 35.0 envelope (drawings; STEP bbox 45.223 x 24.723, case 34.85 incl. bumps) | +0.02 / +0.02 / 0 |
| Case thickness | (box) | **stepped:** 29.0 at the output, 32.0 over most of the body, 35 over two bumps (top centre far end, bottom near the connectors) | new fact |
| Axis from the near end | 12.0 | **10.11** (drawing and STEP) | **-1.89** |
| Vertical corner radius | 1.5 | 2.0 | +0.5 |
| Output boss above the envelope | 2.0 high, Ø10 | none: the face around the output is **2.5 below** the envelope top; the horn hub (Ø10) sits in that recess. Modelled as boss_h 0.05 (token) | -1.95 |
| Horn float (underside above boss) | +0.3 | horn underside **0.25 below** the envelope top -> horn_float -0.30 | -0.6 |
| Spline end above the reference face | 4.5 | 0.75 above the envelope top (3.3 above the recessed face; drawing 3.4) | -3.75 |
| Centre screw | M3 (est.) | M3 x 6 machine screw (drawing) | confirmed |
| Horn OD / thickness | 20.0 / 3.0 | **19.2 / 2.5** (hub Ø10 reaches 2.0 lower) | -0.8 / -0.5 |
| Horn bolt circle / holes | 14 / 4 x Ø2.2 | 14.0 / 4 x Ø2.5 | confirmed / +0.3 |
| Plate seat (horn top) above the envelope top | 5.3 (boss 2 + float 0.3 + horn 3) | **2.25** | **-3.05 per horn side** |
| Back shaft | rotating Ø5.9 25T stub, 3.0 out, boss Ø9 | **static Ø6 boss**, 4.1 below the 29 face (0.55 below the envelope) with a Ø2.6 pilot for a **PA3.0 x 5 self-tapping screw**; the stock **idler horn** (Ø19.2 x 2.2) spins on it inside the back recess | concept change |
| Mounting holes | M3 in the side faces at x 0/24, z -8/-27 | **no side holes**. M2 pilots (Ø1.6) in the top face at x 8.3 / 29.0, y +-10.25 (1.4 deep) and the bottom face at x 8.3 / 32.75, y +-10.25 (2.8 deep); 8 x PA2.0 case screws at x -7.1 (y +-9.35) and 32.75 (y +-10.0). The Feetech drawings dimension a 12.5 pitch near the axis that the STEP does not show: calipers decide | relocated |
| Connectors | +x end face, z -26 | **2 x 5264 3-pin on the back face**, starting 12.5 from the axis toward the long end; plugs insert along the axis from the back | relocated |
| Mass | 0.055 (component default) | catalog mass unchanged (not in the CAD) | - |

Still estimates (2): the connector socket size and the plug + bend room (`cable.socket_wh_mm`, `cable.plug_len_mm`), plus the new
`back_face_x_mm` far edge and `back_plug_room_mm`. The horn screw size (M2 through Ø2.5 holes) is an estimate too.

## Consequences for existing CAD

* Every horn plate sits **3.05 mm closer** to its servo than before; joint stacks get ~6 mm narrower per fork.
* The horn rim is 0.66 mm (radially) from a housing wall that wraps the near end, and plates over the far end sit 0.5 mm above the
  housing's 1.6 mm retaining lip: both below the 1.0 mm moving gap. Housings need a horn relief (r = 9.6 + 1.0, from 1.3 mm below the
  envelope top). `leg_v2.py` (CAD-foundation stand-in, region A) fails its ROM test for exactly this reason (marked xfail with the reason).
* The connectors are on the back face, under the housing cover: covers need a plug window and ~12 mm of plug room below the back face.
  `servo_housing`'s default cover has none (the cable slot it cuts through the far end wall is harmless but not where the plugs are).
