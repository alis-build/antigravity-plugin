#!/usr/bin/env bash
# Per-prompt skill routing. The prompt (lastUserInput) goes to the alis CLI,
# which answers with a line of context or nothing: for "alis, …" and "capture
# this as a skill", how to route; otherwise a skill the Skill store ranks as a
# match for the request ("Skill store match for this request"), which the CLI
# asks for once the prompt passes its gates (alis 1.187.18 or later). The CLI's
# "Possibly relevant Alis skill" notes are dropped: they come from its local
# word-overlap matcher, which suggested unrelated skills too often.
# ALIS_SUGGEST_ALWAYS=0 switches the hook off. Every failure path is silent:
# routing must never break a prompt.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"
[ "${ALIS_SUGGEST_ALWAYS:-1}" != "0" ] || noop
command -v alis >/dev/null 2>&1 || noop

request="$(printf '%s' "$payload" | jq -c '
  select((.lastUserInput // "") | type == "string" and length > 0) |
  select((.conversationId // "") | type == "string" and test("^[A-Za-z0-9_-]{1,128}$")) |
  {hook_event_name: "UserPromptSubmit", session_id: .conversationId,
   cwd: ((.workspacePaths // []) | if type == "array" then (map(select(type == "string"))[0] // "") else "" end),
   permission_mode: "", prompt: .lastUserInput}' 2>/dev/null)" || noop
[ -n "$request" ] || noop

# PreInvocation carries the most recent prompt, so an invocation that is not a
# new prompt would ask about the same one again. Ask once per prompt: remember
# a checksum of the last one asked about, per conversation.
session="$(printf '%s' "$request" | jq -r '.session_id' 2>/dev/null)" || noop
state_dir="${XDG_CACHE_HOME:-$HOME/.cache}/alis/antigravity-suggest"
sum="$(printf '%s' "$request" | jq -r '.prompt' 2>/dev/null | cksum 2>/dev/null)" || noop
if [ -r "$state_dir/$session" ] && [ "$(cat "$state_dir/$session" 2>/dev/null)" = "$sum" ]; then noop; fi
mkdir -p "$state_dir" 2>/dev/null && printf '%s' "$sum" > "$state_dir/$session" 2>/dev/null || true

# Swallow every CLI failure (an older alis that rejects --hook exits 1). The
# codex shape is plain text, which is what an ephemeral message takes.
out="$(printf '%s' "$request" | alis skills suggest --hook --harness codex 2>/dev/null)" || noop
case "$out" in "Possibly relevant Alis skill"*) noop ;; esac
emit_context "$out"
