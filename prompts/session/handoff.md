<!-- prompt: session/handoff · version: 0.1 · tested-on: — · tier: any -->
# Write a handoff

Ask the agent before ending (or let it do this at every checkpoint):

```
Checkpoint now: commit your work, update the task log, then run `oh coord handoff <task> --agent <you>` and fill every section of the file it creates: done so far, next steps in order, gotchas and decisions, files touched, and exact verify commands. Write it so a different agent with zero context can continue without asking questions. Keep it under 60 lines.
```

A good handoff has **concrete next steps** ("add `ankle_roll` to `JOINT_BODY` in simgen.py, then run `oh sim test adam`"), not "continue the work".
