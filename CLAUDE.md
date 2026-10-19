# CLAUDE.md

All agent instructions live in [`AGENTS.md`](AGENTS.md) so every AI tool shares one rulebook. Read it first.

Claude-specific notes:
- Start a session with `oh coord status` to see open/claimed tasks before choosing work.
- Use the profile in `coordination/profiles/` that the user picked (default: `solo`) to decide whether to start parallel sessions or subagents.
- When context has been compacted/summarized, write a handoff immediately (`oh coord handoff <task> --agent <name>`). Then continue.
- Run Python through the repo venv: `.venv/Scripts/python -m openhumanoid …`.
