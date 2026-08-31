---
name: alis-build-capture
description: >-
  Turn work just completed in this session into a reusable Alis Build skill for
  the user's team — like recording a macro after doing the steps by hand.
  ACTIVATE this skill when the user says "make this a skill", "skillify this",
  "capture this as a skill", "save this as a skill", "record this as a skill",
  or "my team should have a skill for this". Also offer it (at most once per
  session, one line, drop it immediately if declined) after completing
  multi-step Alis Build work that required figuring out non-obvious steps AND
  no existing skill covered it. Never offer when an existing skill was loaded
  and followed for the task.
---

# Capture — save just-completed work as a team skill

Turn what was just done in this session into a reusable skill. Think "record a macro after
doing the steps by hand": generalize the steps, not the session.

## Flow

1. **Dedupe first.** Search before creating:

   `alis skills search "<what the work accomplished>" --json`

   On a close match, do NOT create a near-duplicate. Offer instead to:
   - load the existing skill (`alis skills load <id>`),
   - improve it if the user owns it (`alis skills edit <id>`), or
   - send feedback to its owner (`alis skills feedback <id>`).

2. **Confirm scope once.** Propose a skill id (lowercase-hyphen) and a one-line
   description. Ask ONE confirmation covering both the id and what the skill should and
   should not cover. Do not iterate on naming before registering.

3. **Register the draft**:

   `alis skills capture <id> --name "<Display Name>" --description "<description>" --json`

   This reserves the draft in the registry and returns the workspace path. If the
   `capture` subcommand is unavailable, fall back to `alis skills create` with the same
   flags.

4. **Distill into the workspace.** Write/Edit files at the returned path:
   - Generalized, reusable steps with decision points and verification steps — NOT a
     session log.
   - Parameterize specifics: `<project-id>`, `<service>`, `<org>`.
   - Scrub: absolute/home paths, emails, org/project ids, tokens/keys, internal URLs.
   - Description rubric: first clause says what the skill does; then "Use when …" with
     trigger phrases. This text is both the harness trigger and the search-ranking
     surface — write it for both.
   - Optionally add `references/` files for a scrubbed worked example.

5. **Write the eval while ground truth is fresh.** Fill `evals/cases.yaml` with 1-2 cases
   whose prompt is a generalized version of the task actually just done.

6. **Review in-session.** Show the user the frontmatter description and the step headings
   (not the whole file); iterate on their comments. Mention that the workspace persists at
   `~/.alis/skills/workspaces/<id>/` and can be continued later via
   `alis skills open <id>` or the TUI walkthrough.

7. **Publish only on explicit approval**:

   `alis skills publish <id>`

8. **After publish, offer ONCE**:
   - `alis skills evaluate <id>` — recommended before team-wide sharing.
   - `alis skills share <id> --domain` (whole team) or `--email <addr>` (individual).

   Frame it: "your team will find it by just describing the problem — discovery surfaces
   it automatically."
