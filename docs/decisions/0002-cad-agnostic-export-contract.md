# 0002: CAD-agnostic via an export contract; build123d is the AI-default backend

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit

## Context
Humans use Onshape, SolidWorks, FreeCAD, Fusion. AI agents can fully author code-CAD but only partially drive GUI CAD (the Onshape MCP is limited and SolidWorks has no agent API here). Sim and BOM need geometry, mass properties, and kinematics regardless of tool.

## Decision
The pipeline never reads native CAD files. Every backend must produce the **export contract** (`cad/EXPORT_CONTRACT.md`): STEP + STL per part, a mass-properties YAML, and a robot description (MJCF or URDF). Each variant picks `cad.backend`. For AI-driven one-shot design the default is **build123d** (Python, OpenCascade). It is fully scriptable, diffable, and parametric from the spec. Humans may re-surface shells in any tool as long as exports meet the contract.

## Consequences
- (+) Anyone can contribute in their tool. Agents can generate whole robots end-to-end.
- (+) Onshape users can use onshape-to-robot. SolidWorks users can use the SW-to-URDF exporter. Both feed the same contract.
- (−) Native-file edits in GUI tools aren't diffable. Exports plus a pinned source link/version are mandatory.

## Alternatives considered
- Onshape only: cloud lock-in, limited agent control.
- SolidWorks only: paid, Windows-only, no agent API.
- OpenSCAD: weak at the smooth surfaces the design language needs.
