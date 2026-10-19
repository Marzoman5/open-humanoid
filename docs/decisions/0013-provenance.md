# 0013: Provenance for every number: spec schema v0.2 adds a `provenance:` map

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit (schema) · **Deciders:** maintainer (via ADR 0011), harness session T-0015
- **Evidence:** research/ai-engineering/RECOMMENDATIONS.md §D4, ADR 0011 §3, ADR 0012 §4 (the DrEureka lesson: guessed ranges cause hardware faults)
- **Amends:** `schemas/spec.schema.json` (v0.1 → v0.2). `schemas/catalog-part.schema.json` is unchanged.

## Context
AGENTS.md rule 6 ("be honest about numbers") was advisory. The catalog already carries `source` and `verified` per part, but the tuned constants in a spec (`analysis:` safety and dynamic factors, `mass_model:` structure mass, waste factor…) are plain numbers with at most a YAML comment. Those constants decide whether sizing says "feasible", so they need the same discipline as prices.

## Decision
1. **Spec schema v0.2** adds an optional top-level `provenance:` map. Keys are dotted paths into the spec (`analysis.safety_factor`). A key covers its children (`analysis.dynamic_factor` covers `.walk` and `.run`). A value is either a source string or `{source, note?, as_of?}`.
2. A `source` is one of: an `http(s)` URL · a path to a file in this repo (optionally `#anchor`) · `measurement:<repo path>` · `estimate: <why>`. `estimate:` is allowed and honest, but it is counted separately and is never "verified".
3. **Schema versions.** `schema_version` accepts `"0.1"` and `"0.2"`. Existing 0.1 specs (Adam) still validate. A variant opts in to 0.2 by bumping the field and adding `provenance:`. Nothing else changes in v0.2.
4. **What must have provenance:** every numeric leaf under `analysis:` and `mass_model:` (`openhumanoid/provenance.py: TUNED_SECTIONS`). Adding another section is a one-line change plus an ADR note.
5. **Catalog:** every part needs a non-empty `source` and a boolean `verified`. `verified: true` with an `estimate:` source, or with no URL/file/measurement, is an inconsistency. `verified: false` with an `estimate:` source is the normal state until T-0002 checks live listings, and is counted as an estimate.
6. **Enforcement is warn-first.** `oh check provenance [variant]` prints every problem. The pass/fail thresholds live in `pipeline/gates.yaml` under `G-provenance` (hook-protected). Today they fail on a catalog part with no source/verified or a verified-but-estimate part, and merely count spec and estimate problems. Tightening a number is an ADR task.

## Consequences
- (+) A reviewer, CI and the Stop hook can see which constants are measured and which are guesses.
- (+) The Adam spec can adopt it as P2 produces measurements, without a flag day.
- (−) Adam's spec doesn't have a `provenance:` map yet (8 constants flagged). Adding it is a spec edit outside the harness task, and each entry should be real, not filler.
- (−) Presence of a citation isn't truth. `oh check provenance` checks that a cited file exists, not that it supports the number. Review stops and the separate critic remain responsible for that.

## Alternatives considered
- Inline `# source:` YAML comments: not machine-checkable (comments are dropped by the parser).
- Per-field `{value, source}` objects in the spec: breaks every existing reader of the spec.
- Making provenance mandatory immediately: would fail Adam's spec and block unrelated work; warn-first with a gate threshold gets there without a flag day.
