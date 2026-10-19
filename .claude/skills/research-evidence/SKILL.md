---
name: research-evidence
description: Run an Open Humanoid research task (P1 evidence base, methods review, reuse/license audit) so its numbers can be trusted. Use when an agent must gather facts, specs, benchmarks, prior art or licenses that design decisions will rest on.
---

# Research that design can stand on

Written after the first real P1 run (2026-10-19, T-0012/13/14). Each rule exists because skipping it caused a real problem; see `coordination/LESSONS.md`.

## Brief
- Pose **open questions**. Anything the requester names (a tool, a diagnosis, a likely answer) is a hypothesis to test, not a conclusion. Say so in the brief. Anchoring happened once already.
- Ask explicitly: "Is our overall approach sound, or do successful practitioners do this differently?"

## Gathering
- Fan out with parallel search subagents (Sonnet is enough). Keep synthesis for yourself.
- Prefer primary sources: papers (read the HTML full text, not the abstract), official docs, repo files via `gh api`, datasheets, manufacturer pages. Retailer listings are secondary.
- Every number carries a URL and an access date. Unknown means `null`, never a guess.
- Licenses: read the actual LICENSE file (root *and* sub-folders, since CAD is often licensed differently from code). README claims don't count.
- Run experiments when cheap. A blind-critic test and the Windows install checks were worth more than pages of reading.

## Verification pass (mandatory before anyone builds on it)
- Independent agents re-open every decision-relevant claim at its source and mark it **verified / corrected / unsupported / unreachable**. Write `VERIFICATION.md` as a claim → status → evidence table.
- In the first run this changed real numbers: 1 claim removed, 7 corrected out of 41, plus a voltage mix-up and a hallucinated statistic.
- State the verifier's limits (summarizing fetchers, 403s, truncated pages).

## Output
- One `SUMMARY.md` (≤ 1 page, decision-relevant findings, ⚠ where it contradicts current assumptions) plus per-topic files plus machine-readable YAML for tools.
- End with what is still unknown and can only be **measured**.
