# CAD cheat-sheet (build123d + our helpers)

*Research C5: there is no build123d benchmark and less training data than for CadQuery, so this page lists what we actually hit. Method and
checks: [cad-foundation.md](cad-foundation.md). Every ```` ```python golden ```` block below is executed by `tests/test_cad_foundation.py`.*

## Rules that prevent most failures

1. **Never write a loft, shell, offset or tangent boolean by hand.** Use `loft_shell`, `servo_housing`, `apply`. If you must use a raw boolean, wrap it in `safe_cut` / `safe_union`.
2. **Frames first.** Get placements from `interfaces.load(spec).servo_loc(joint)` and from component `.frames`; never type a servo dimension.
3. **Union before you cut.** Build the raw bodies, then `Housing.build(loc, adds=[...])` or `apply(base, *features)`: additions first, cuts second. A union after a pocket refills it.
4. **Numbers come from `dfm.yaml`**: `dfm.clearance("slip")`, `dfm.hole_d(3.0)`, `dfm.min_wall("structural")`.
5. **After every part run the gate** (`geometry_gate.check_part`); after every assembly the ROM sweep and `access.analyse`.
6. **Measure, don't look.** A render cannot check a size (about 27 points worse than code in BenchCAD).

## build123d facts we tripped over

| Topic | Do this |
|---|---|
| Algebra vs builder mode | We use **algebra mode** (`a + b`, `a - b`, `a & b`, `Pos(x,y,z) * shape`). `BuildPart` hides the order of operations; avoid it in helper code. |
| Placement | `Pos(x,y,z) * shape` moves, `Rot(rx,ry,rz) * shape` rotates about the shape's origin (degrees), `Location` composes: `loc * shape`. Helpers use `core.loc_from(origin, z_dir, x_dir)`. |
| Points through a frame | `Location * Vector` does **not** work. Use `(loc * Location((x, y, z))).position` (a `Vector`). |
| Box/Cylinder | `Box(l, w, h)` is centred; zero or negative size raises `Standard_DomainError`. `core.box_at(loc, size, centre)` and `core.cyl_along(loc, d, h, z0)` stand a cylinder on a plane. |
| Selecting edges | `shape.edges().filter_by(Axis.Z)` = edges parallel to Z; `.filter_by(GeomType.CIRCLE)`; `.sort_by(Axis.Z)[-1]` highest; `faces().sort_by(Axis.X)[0]`. |
| Fillet | `fillet(shape.edges().filter_by(Axis.Z), r)`; r must be under half the thinnest adjacent face (we clamp: `min(r, 0.45 * span)`). |
| Hex socket | `extrude(RegularPolygon(radius, 6), amount=h)`; radius is the circumradius (`across_flats / sqrt(3)`). |
| Volume checks | `shape.volume` (mm3), `shape.is_valid`, `len(shape.solids())`. `a & b` gives the overlap; `shape.is_inside(Vector)` for a point. |
| STEP / STL | `export_step(shape, path)`, `import_step(path)`; `shape.tessellate(tol, ang)` -> vertices, triangles (merge vertices before trimesh). |
| Text | `Text` needs a font; engraving can fail headless, so gauge labels are optional. |
| `offset()` | Reports `is_valid=True` on shells with a wrong volume. Never trust it; use `loft_shell` (outer - inner) and check the volume. |

## Our helpers in one glance

```text
core:      apply(base, *features) -> (shape, sites)     safe_cut / safe_union     overlap_volume / min_distance     Site / FeatureResult
features:  servo_pocket   horn_mount   idler_seat   insert_boss   screw_clearance / counterbore   magnet_boss
           cable_channel  keepout      split_for_bed loft_shell    screw_length_for  bolt_circle
housing:   servo_housing(actuator, cover_t, idler) -> Housing.build(loc, adds=[...], extra=[...])  /  .placed_cover(loc)
checks:    geometry_gate.check_part / check_assembly / run_gate     rom.sweep_all / check_pose     access.analyse
```

## Golden example 1: a servo cradle with its cover

```python golden
from openhumanoid.cad.components import get
from openhumanoid.cad.core import overlap_volume, min_distance
from openhumanoid.cad.housing import servo_housing

servo = get("sts3215")                          # frame: origin on the output axis, +z out of the horn face
h = servo_housing("sts3215-12v")                # block + pocket + far-end lip + cable slot + cover with 2 counterbored screws
assert overlap_volume(h.shape, servo.shape) < 0.5                       # the servo drops in
assert abs(min_distance(h.shape, servo.params["case_shape"]) - 0.15) < 0.02    # slip fit, 0.15 mm per side
assert [s.kind for s in h.sites + h.cover_sites].count("screw") == 2    # sites feed the assembly-access check
```

## Golden example 2: a plate on a servo horn

```python golden
import build123d as bd
from openhumanoid.cad import features as F
from openhumanoid.cad.components import get
from openhumanoid.cad.core import apply, box_at, loc_from

horn = get("horn-25t")                                           # 3 mm thick; the horn_seat frame sits on the servo boss
plate = box_at(bd.Location(), (44, 30, 4.3), (0, 0, horn.params["thickness"] + 4.3 / 2))      # in the horn_seat frame
shape, sites = apply(plate, F.horn_mount("sts3215-12v", plate_t=4.3, mode="flat"), name="demo_plate")
assert shape.volume < plate.volume and len(sites) == 5                       # centre screw + four horn screws
assert all(s.kind == "screw" and s.tool_d == 6.0 for s in sites[1:])         # M2 low-head: 6 mm tool corridor
try:
    F.horn_mount("sts3215-12v", plate_t=3.2)                                 # too thin under the counterbore: refuses
    raise SystemExit("should have raised")
except Exception as e:
    assert "plate_t" in str(e)
```

## Golden example 3: bosses, fasteners and a bed split

```python golden
import build123d as bd
from openhumanoid.cad import dfm, features as F
from openhumanoid.cad.core import apply, loc_from

beam = bd.Box(450, 40, 30)                                                   # longer than the 220 x 220 x 250 bed
feats = [F.insert_boss("M3", at=loc_from((x, 0, 15), (0, 0, 1))) for x in (-200, 0, 200)]        # insert pockets on the top face
beam, sites = apply(beam, *feats, name="beam")
pieces = F.split_for_bed(beam, [220, 220, 250], part="beam")                 # cuts at the smallest sections, dowel pockets on both faces
usable = dfm.bed_usable([220, 220, 250])
assert len(pieces) == 3 and len(sites) == 3
for _, s in pieces:
    b = s.bounding_box().size
    assert all(e <= u for e, u in zip(sorted([b.X, b.Y, b.Z], reverse=True), sorted(usable, reverse=True)))
assert sum(len(s.solids()) for _, s in pieces) == 3                         # the cut avoided the insert at x = 0 (+-3 mm)
```

## When a check fails

| Message | Meaning | Usually fix by |
|---|---|---|
| `CadOpError: ... expected one solid` | a body floats free or a cut split the part | check the plate/column actually touches the housing; add overlap |
| `min_wall: N mm3 thinner than 1.6` (with a location) | counterbore, pocket or hole too close to an edge or to each other | move the hole, widen the part, thicken the plate |
| `expect:...: hole ... is blocked` | a hole is not where `interfaces.yaml` says | the part was built from different numbers; rebuild from the interface frame |
| `CLASH a x b` in the gate | the parts overlap at the stand pose | change the layout stand-off before the part |
| ROM `limits [None, 29.06]` | contact at that angle (pair named) | stand-off, web radius, or record a CAD-limited range for the concept loop |
| `NO VALID ORDER (precedence cycle)` | two parts each block the other's insertion | split one of them (removable plate/cap) |
| `UNREACHABLE screw` | the owner or its mate covers the tool corridor | assemble that joint earlier (split the part) or add an access hole |
