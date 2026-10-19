# 0001: Open Humanoid is a toolkit; robots are variants

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit

## Context
The goal is that anyone can make the humanoid they want, at $400 or $100k, modular or not, with or without an LLM. A repo that is "one robot plus docs" would bake one robot's assumptions into everything.

## Decision
Framework, catalog, modules, prompts, and tools are variant-agnostic. Each robot is a folder in `variants/` driven by `spec.yaml`. Specs can `extends:` a parent. Adam is the first reference variant and the test bench for the toolkit.

## Consequences
- (+) New robots start from proven tools. Adam work automatically improves the toolkit.
- (−) Every tool needs a spec knob instead of a constant, which is more design work up front.
- (−) Tools must be tested against at least one non-Adam spec (tests use a synthetic large variant) to catch Adam-isms.

## Alternatives considered
- Single robot repo, fork to customize: forks diverge and tools never get shared.
