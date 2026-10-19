<!-- prompt: analysis/validate-sizing · version: 0.1 · tested-on: adam@0.1.0 · tier: mid -->
# Validate sizing against sim and hand calcs

```
For variant <id>: run `oh size <id>` and `oh sim test <id> --json`. For the 3 joints with the lowest margins in generated/sizing.md:
1. Recompute the static torque by hand from generated/sizing.json (geometry_m, segment_mass_kg), showing your working.
2. Compare it to the sim's peak_torque_fraction_of_stall × stall torque for that joint.
3. If sizing and sim disagree by more than 30%, find out why (model assumption, posture, mass distribution) and propose a fix to openhumanoid/sizing.py or the spec's analysis constants, with evidence.
Report a table: joint | sizing static | hand calc | sim holding | verdict. Do not change files unless I approve.
```
