# Prompt library

Prompts here are **tools**: versioned, tested on a real variant, and written to work with any capable agent.

| Prompt | Use it to | Status |
|---|---|---|
| [oneshot/build-a-humanoid.md](oneshot/build-a-humanoid.md) | Run the whole pipeline (P0–P9) for a variant, checkpointed | v0.1 |
| [sourcing/part-sourcing.md](sourcing/part-sourcing.md) | Verify/refresh catalog prices and specs; source a BOM | v0.1 |
| [session/resume.md](session/resume.md) | Start a fresh session on an in-flight task | v0.1 |
| [session/handoff.md](session/handoff.md) | Write a good handoff before stopping | v0.1 |
| [analysis/validate-sizing.md](analysis/validate-sizing.md) | Cross-check sizing against sim and hand calcs | v0.1 |

## Header block (required for every prompt)

```markdown
<!-- prompt: <area>/<name> · version: X.Y · tested-on: <variant@version> · tier: top|mid|light -->
```

`tier` tells orchestrators which model class the prompt needs (see `coordination/profiles/`). When you improve a prompt after a real run, bump the version and note what changed at the bottom.
