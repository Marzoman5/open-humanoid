# Commander log

Running log of commander decisions and overnight progress. Newest at the bottom. Provisional decisions are marked **PROVISIONAL**, for maintainer review.

## 2026-10-19 night (unattended run)
Authorized by the maintainer: proxy review at R1/R2a (provisional), background agents, spend for quality, provisional trade-offs by priority (walk > not-a-toy > wave/dance > pickup).

- [start] Wave 1 reviewed (harness 66 tests, design tooling 41 tests). Live hook test: deny rules OK (4/4); Stop hook did not block. Diagnosing before merge.
- [hooks] Live test in a standalone clone: PreToolUse PASS (4 deny, 1 warn, 2 allow); Stop logic PASS (didn't block live only because the gates were PASS at HEAD; blocks once when forced). Defect: the SessionStart smoke ran under system Python, giving a false FAIL. Fix sent to the harness session before merge. Known gap: P2 has no gates yet, so Stop can't block P2 tasks until G-envelopes exists.
- [concept] T-0017 concept engine tooling started as a background agent (Sonnet, worktree).
