# Design language (toolkit default)

Variants may override this with `variants/<id>/design-language.md`. This is the default Open Humanoid look: **sleek, not toy-like**.

## The core trick: frame + shell

Every body segment has two layers:

| Layer | Job | Rules |
|---|---|---|
| **Frame** | Carries load, holds actuators, routes cables | Optimized for stiffness and printability. Can be ugly. Never visible in the finished robot. |
| **Shell** | Gives the look | Smooth, continuous surfaces. Snap-fit or magnet-mounted. Fits over the frame with a 1–2 mm gap. Replaceable and re-skinnable. |

Modders re-skin by replacing shells only. Variants with `architecture.shell: false` skip shells (lab/test builds).

## What "sleek" means here

1. **No visible servo boxes.** Actuators sit inside segment volumes. Horns and brackets hide under shells.
2. **Continuous silhouettes.** Thigh-to-shank and torso-to-pelvis read as one flowing form. Joint gaps are deliberate dark recesses, not exposed mechanisms.
3. **Big fillets, no hard boxes.** Minimum outer radius is about 3% of segment width. Prefer G2 lofts over chamfers.
4. **Adult proportions, not chibi.** The head is about 13–15% of height (toys use 20%+). Long legs. Narrow waist.
5. **Two-tone at most.** A main shell color plus a dark recess color (joints, face plate, gaps). One accent is allowed: a light strip or face display.
6. **Visible cables: zero.** Wires run through hollow joints or along the inside of the frame.
7. **Faceless or minimal face.** A smooth visor/face plate. Sensors (camera, IMU) hide behind it.

## Practical constraints that serve the look

- Shell wall 1.2–2 mm (FDM), split along natural panel lines, with seams placed where they read as design lines.
- Print shells with the visible face up or vertical, so supports land on hidden surfaces.
- Magnets (6×3 mm N52) or snap tabs, no visible screws on shells.

## References (to be filled by the variant owner)

Add 2–5 reference images/links per variant in `variants/<id>/design-language.md` with one line on what to take from each. *(Adam: see task T-0003.)*
