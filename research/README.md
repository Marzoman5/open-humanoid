# research/: Open Humanoid evidence base (v1)

Cited facts that feed virtual prototyping (sizing, MuJoCo actuator models, randomization, reference motions). Nothing here is a design decision; decisions go in `docs/decisions/`.

## Layout

| Path | What | Machine-readable |
|---|---|---|
| `SUMMARY.md` | 10 findings that matter for Adam, incl. contradictions of current assumptions | |
| `actuators/<id>/` | `datasheet.yaml` (official specs, voltage stated), `measured.yaml` (published identified models), `notes.md` (field behavior, failures) | yes |
| `robots/benchmarks.{yaml,md}` | Comparable humanoids, lessons, scaling fits | yes |
| `methods/a-…e-*.md` | Cited method summaries, each ending in "Recommendation for Open Humanoid" | `domain_randomization_ranges.yaml`, `print_materials.yaml` |

Actuator ids: `feetech-sts3215`, `feetech-sts3250`, `dynamixel-xl430`, `dynamixel-xm430`, `robstride-02/03/04`.

## Citation rules

1. Every number carries a source URL and `accessed: 2026-10-19` (YYYY-MM-DD, the date the page was read).
2. **Unknown is `null`. Never guess or interpolate** (AGENTS.md rule 6). A derived number must say it is derived and show inputs.
3. State the voltage/conditions a spec was taken at. Mark vendor-claimed vs independently measured.
4. Prefer primary sources (datasheets, papers, official repos). Retailer pages and blogs are allowed only if labelled as such.
5. Conflicting sources are listed side by side, not merged.

## How agents should use it

- Sizing/sim: read values from `actuators/*/datasheet.yaml` and `measured.yaml`; do not copy numbers into code. If a needed field is `null`, report it as an open measurement (bench test) instead of assuming.
- Treat vendor "stall torque" as a ceiling, not a working number; see `SUMMARY.md` for continuous-torque evidence.
- Before changing an assumption in `openhumanoid/sizing.py` or a spec `analysis:` block, cite the file and key here in the decision record.
- New evidence: add it with source + date, keep entries small, bump nothing else. Stale (>12 months) entries should be re-verified.
- Known limitations: the Feetech datasheet PDF is image-only, so STS3215 values are retailer-sourced; several sources were reached only through search summaries and are flagged in-file.
