# Adam design language

Inherits [docs/design-language.md](../../docs/design-language.md) (frame + shell, sleek, not toy-like). **Status: references confirmed by maintainer (2026-10-19). Direction below is the working brief. Confirm or adjust it at the first concept review (review gate R2).**

## References and what to take from each

| Reference | Take | Leave |
|---|---|---|
| **Tesla Optimus** | Human proportions. White shells over a black under-structure. Glossy black faceless head visor. Tapered limbs with a slight "muscle" swell. Black pelvis/waist band that separates chest from legs. | Complex hands (out of budget). Exposed rear actuators. |
| **Electric Atlas (Boston Dynamics)** | Capsule and cylinder primitives blended smoothly. Monochrome, calm surfaces. A ring-light face as the single expressive element. Zero visible cables. Compact hips. | Inhuman joint ranges as a styling statement. The industrial grey palette. |
| **Apple industrial design** | Unibody feel. Continuous-curvature (G2) blends. A few consistent radii. Tight, even parting lines. No visible fasteners. Matte finish. Restraint: one material look, one accent. | Precision-machined tolerances FDM can't hold. Fake it with consistent gaps. |

## Adam rules

1. **Palette:** matte warm white shells (PLA "matte white" or primed and painted) plus graphite/black for joint recesses, pelvis band, visor, and under-frame. **One accent:** an optional thin white light ring around the visor (Atlas nod; plugin later, adds about $3 of LEDs).
2. **Head:** pill/capsule form, about 14% of height. The whole front is one glossy black visor (print in black PETG and polish, or use a thermoformed tinted shell). No eyes, no mouth.
3. **Torso:** chest shell flows into the shoulder caps without a break. The waist narrows to the black pelvis band. The back is one continuous panel that hides the battery and Pi.
4. **Limbs:** tapered capsules. The thigh is widest at the hip and tapers to the knee. The shank has a calf swell in its upper third and narrows to the ankle. Upper arm and forearm read as one line when straight.
5. **Joints:** every joint is a dark recessed band 2–3 mm deep between two white shells. Servo bodies and horns are never visible from the front or sides.
6. **Surfaces:** G2 blends, few radii (at Adam scale: 3 mm minor, 8 mm major). No flat face larger than about 30% of a segment's visible area unless it's a deliberate plane. No visible screws (magnets or snap tabs).
7. **Parting lines:** at most one visible seam per segment, on side planes or along the dark joint bands. Consistent 0.8 mm gap (the FDM-honest version of Apple tightness).
8. **Feet:** low, sleek wedge shells with a TPU sole. The black sole reads as part of the dark structure.

## Packaging constraints the look must respect (from generated/sizing.json)
- At h = 0.50 m the thigh is about 112 mm long and holds the hip-pitch **and** knee STS3215 servos (each about 45 × 35 × 25 mm). The outer shell section must clear about 32 × 50 mm plus 2 mm frame walls plus a 1.5 mm shell gap. That sets the minimum thigh "width". Design the taper around it.
- Shells: 1.6 mm walls, printed visible-face-out, 0.12 mm layers for curved faces.

## Review gates (what the maintainer will look at)
- **R2 concept:** front/side/¾ renders of the shell massing over the frame (`oh render adam`), against the three references.
- **R3 final:** detailed renders plus a print-layout image (parts on a 220 × 220 bed).
