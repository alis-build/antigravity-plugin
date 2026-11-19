#!/usr/bin/env bash
# Per-prompt skill routing. By default (ALIS_SUGGEST_ALWAYS=0), only prompts
# that mention "alis" or "skill" are sent to `alis skills suggest --hook`, so
# routine coding/test turns pay no synchronous network latency or false-positive
# UI cards (skills/alis-discover handles platform-shaped discovery quietly).
# Set ALIS_SUGGEST_ALWAYS=1 to query the Skill store on every prompt, or
# ALIS_SUGGEST_ALWAYS=off to disable the hook completely.
# Every failure path is silent: routing must never break a prompt.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"

mode="${ALIS_SUGGEST_ALWAYS:-0}"
[ "$mode" != "off" ] || noop
command -v alis >/dev/null 2>&1 || noop

request="$(printf '%s' "$payload" | jq -c '
  select((.lastUserInput // "") | type == "string" and length > 0) |
  select((.conversationId // "") | type == "string" and test("^[A-Za-z0-9_-]{1,128}$")) |
  {hook_event_name: "UserPromptSubmit", session_id: .conversationId,
   cwd: ((.workspacePaths // []) | if type == "array" then (map(select(type == "string"))[0] // "") else "" end),
   permission_mode: "", prompt: .lastUserInput}' 2>/dev/null)" || noop
[ -n "$request" ] || noop

prompt_text="$(printf '%s' "$request" | jq -r '.prompt' 2>/dev/null)" || noop
if [ "$mode" != "1" ]; then
  printf '%s' "$prompt_text" | grep -qiE 'alis|skill' || noop
fi

# PreInvocation fires before every model call and carries the most recent
# prompt each time, so a turn with tool calls would ask about the same prompt
# again and again. Ask once per prompt: remember a checksum of the last one
# asked about, per conversation.
session="$(printf '%s' "$request" | jq -r '.session_id' 2>/dev/null)" || noop
sum="$(printf '%s' "$prompt_text" | cksum 2>/dev/null)" || noop
if [ -r "$state_dir/$session.prompt" ] && [ "$(cat "$state_dir/$session.prompt" 2>/dev/null)" = "$sum" ]; then noop; fi
mkdir -p "$state_dir" 2>/dev/null && printf '%s' "$sum" > "$state_dir/$session.prompt" 2>/dev/null || true

# Swallow every CLI failure (an older alis that rejects --hook exits 1).
out="$(printf '%s' "$request" | alis skills suggest --hook --harness codex 2>/dev/null)" || noop
case "$out" in ""|"Possibly relevant Alis skill"*) noop ;; esac
# Left as a system message, so it is still there on a later turn ("is that
# from a skill?"). The CLI caps how many a conversation gets.
case "$out" in
  *"Skill "[Ss]"tore match"*) out="$out
If you answer without loading it, name the skill in your answer so the user knows it exists." ;;
esac
emit_system "$out"
