---
name: alis-build-discover
description: >-
  Find and load the right Alis Build skill from the registry. ACTIVATE this
  skill when the task is platform-shaped: creating or changing a product,
  neuron, block, or landing zone; editing .proto contracts or running Define;
  Spanner schemas or protobundles; Pub/Sub event handlers; Terraform under a
  neuron's infra/; generated packages failing to resolve; playground tests;
  migrating legacy proto imports; ADK agents. Also on explicit asks: "find a
  skill for …", "is there a skill for …", "alis, …", "hey alis". Do NOT
  activate for: merely being inside an alis.build workspace, Makefiles and
  local dev tooling, generic Go/JS bugs or test authoring, git operations,
  reading logs, or when a loaded Alis skill already covers the task. Probes
  the local catalog first (instant), loads the chosen skill, which then owns
  execution.
---

# Discover — find and load the right Alis Build skill

Route quietly: find the best skill, load it, hand over. No preamble about
running discovery.

## Flow

1. **Infer the intended outcome** from the request and workspace context.

2. **Probe locally** (~40ms, no network):

   `alis skills suggest "<intended outcome>" --json`

   A candidate is real only when its `distinctive` score is ≥ 3 (on a CLI
   that does not report `distinctive`, require `score` ≥ 5). Below that,
   there is no skill — say nothing about discovery and do the work.

3. **Unsure between candidates?** `alis skills preview <id>` is a cheap fit
   check before committing to a load.

4. **Load and follow**: `alis skills load <id> --via dispatcher`. The loaded
   skill owns execution — mention it in one clause, then follow its workflow.

5. **Registry search is the exception, not the default**:
   `alis skills search "<outcome>" --limit 3 --json` only when the user
   explicitly asked to find a skill, or the local probe was genuinely
   ambiguous. On any failure, fall back to the probe result and continue —
   never block, never retry.

## Rules

- Discovery runs at most once per task: after a miss, do not re-probe on
  follow-up prompts about the same piece of work.
- If the user asked for a skill and nothing fits, say so and offer to file
  it: `alis skills request --name "…" --description "…"`.
- If the `alis` CLI is absent, continue helping without a skill.
