---
name: handoff
description: Continue the current antigravity CLI session on an enrolled Alis workstation in herdr. Use when the user wants to hand off work or close their laptop while it continues remotely.
---

Use the Alis coordinator; never copy agent homes, kill processes, invent session IDs,
or launch a second continuation yourself. This skill applies to the native CLI;
IDE and desktop app sessions need a verified CLI registration.

1. Use the current session ID from hook context (or the agent's session environment).
   Run `alis workstation handoff targets --json`; select the only enrolled target
   in this organisation, or ask which target if several qualify.
2. Native cross-machine resume for antigravity is not enabled in this release. Tell
   the user the fallback starts a **new session with continuation context** and
   obtain their choice before proceeding. Never silently downgrade to a summary.
3. After that choice, write a short continuation note with the task, constraints,
   completed external actions, exact active Alis operation IDs, and the next step.
   Run `alis workstation handoff --agent antigravity --mode summary --session <id>
   --to <alias> --instruction '<note>' --json` as one standalone invocation with
   literal shell quoting. Do not wait for remote operations to finish; stop only
   their local watchers once the operation IDs and any pending results are saved.
4. End this turn after the coordinator returns. It waits for a recoverable
   boundary and opens an independent progress window. Polling from this source
   turn prevents the boundary. Keep the laptop open until `safe_to_close: true`.

Use `alis workstation handoff status <id> --watch --json` from another terminal.
Use `alis workstation handoff open <id>` to open the continuation in herdr.
Spaces use `alis.os`, tabs `cli.v1`, with one pane per continuation. Paired build
and Define worktrees isolate simultaneous handoffs; local files stay intact.
Normal destination trust and permission prompts still apply. Unknown background
work blocks handoff rather than being abandoned. `cancel <id>` releases the source
claim only once any launched remote continuation has acknowledged cancellation.
Uncertain remote status never permits starting a second copy locally.
