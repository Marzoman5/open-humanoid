<!-- prompt: session/resume · version: 0.1 · tested-on: — · tier: any -->
# Resume a task in a fresh session

Paste this line (fill the task ID and your agent name) into a new session at the repo root:

```
Read AGENTS.md, then run `oh coord status` and `oh coord resume T-____`. You are agent `____`. Continue that task from its latest handoff: verify the "How to verify" commands still pass, then do the "Next steps" in order. Follow the checkpoint rules. If the task is claimed by another agent, stop and tell me.
```

Token tip: this costs about 3–5k tokens of reading before useful work starts, much less than re-explaining the project.
