#!/usr/bin/env bash
# Keep the Python bridge's native payload handling when a runtime is available.
# Without one, skip ordinary sessions but retain the source handoff fence.
set -eu
agent=antigravity
hook_dir=$(dirname "$0")
payload=$(cat 2>/dev/null) || exit 0
if out=$(printf '%s' "$payload" | "$hook_dir/run-python.sh" --required "$hook_dir/handoff.py" "$agent" "$@"); then
  [ -z "$out" ] || printf '%s\n' "$out"
  exit 0
else
  status=$?
  [ "$status" -eq 69 ] || exit "$status"
fi

event=${1:-}
if command -v jq >/dev/null 2>&1; then
  sid=$(printf '%s' "$payload" | jq -er '
    (.session_id // .conversationId) | select(type == "string") |
    select(length >= 1 and length <= 128 and (test("[^A-Za-z0-9_-]") | not))
  ' 2>/dev/null) || exit 0
  [ -e "$HOME/.alis/handoff-sessions/$agent--$sid.claim" ] || exit 0
  if [ -z "$event" ]; then
    event=$(printf '%s' "$payload" | jq -r '.hook_event_name // "" | select(type == "string")' 2>/dev/null) || event=
  fi
else
  # Without a JSON parser, never guess the session from tool-controlled text.
  # Conservatively pause if this agent has any outstanding source claim.
  claimed=0
  for claim in "$HOME/.alis/handoff-sessions/$agent--"*.claim; do
    [ ! -e "$claim" ] || claimed=1
  done
  [ "$claimed" -eq 1 ] || exit 0
fi

reason="A workstation handoff may own this session, but its Python hook is unavailable. Restore Python and check handoff status before continuing locally."
case "$agent:$event" in
  codex:PreToolUse)
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason" ;;
  codex:UserPromptSubmit|codex:Stop|codex:)
    printf '{"continue":false,"stopReason":"%s"}\n' "$reason" ;;
  antigravity:PreToolUse)
    printf '{"decision":"deny","reason":"%s"}\n' "$reason" ;;
  antigravity:PreInvocation)
    printf '{"injectSteps":[{"ephemeralMessage":"%s"}]}\n' "$reason" ;;
  antigravity:Stop)
    printf '{"decision":"stop","reason":"%s"}\n' "$reason" ;;
esac
exit 0
