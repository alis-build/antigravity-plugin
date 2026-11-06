#!/usr/bin/env bash
# The CLI owns native payload handling. The legacy path preserves active
# handoff claims while a person upgrades an older CLI.
set -eu
agent=antigravity
payload=$(cat 2>/dev/null) || exit 0
if out=$(printf '%s' "$payload" | alis hooks run --protocol 1 --harness "$agent" --handler handoff --event "${1:-}" 2>/dev/null); then
  [ -z "$out" ] || printf '%s\n' "$out"
  exit 0
fi

# Compatibility with CLIs predating native hook protocol 1: their coordinator
# already owns handoff state. jq supplies only the older wire-format adapter.
if command -v jq >/dev/null 2>&1; then
  if legacy=$(printf '%s' "$payload" | jq -ce --arg agent "$agent" --arg event "${1:-}" '
    select(type == "object") |
    (.session_id // .conversationId) as $sid |
    select($sid | type == "string" and length >= 1 and length <= 128 and (test("[^A-Za-z0-9_-]") | not)) |
    .agent = $agent | .integration = 2 |
    if $event != "" then .hook_event_name = $event else . end
  ' 2>/dev/null); then
    if response=$(printf '%s' "$legacy" | alis workstation handoff _hook 2>/dev/null); then
      [ -n "$response" ] || response='{}'
      if printf '%s' "$response" | jq -e 'type == "object"' >/dev/null 2>&1; then
        event=$(printf '%s' "$legacy" | jq -r '.hook_event_name // ""')
        printf '%s' "$response" | jq -c --arg agent "$agent" --arg event "$event" '
          select(.continue == false) |
          (.stopReason // "This session is handing off to a workstation.") as $reason |
          if $agent == "antigravity" then
            if $event == "PreToolUse" then {decision:"deny",reason:$reason}
            elif $event == "PostInvocation" then {terminationBehavior:"terminate"}
            elif $event == "PreInvocation" then {injectSteps:[{ephemeralMessage:$reason}]}
            else {decision:"stop",reason:$reason} end
          elif $event == "PreToolUse" then
            {hookSpecificOutput:{hookEventName:$event,permissionDecision:"deny",permissionDecisionReason:$reason}}
          else . end
        ' 2>/dev/null || true
        exit 0
      fi
    fi
  fi
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

reason="A workstation handoff may own this session, but its CLI hook is unavailable. Upgrade alis and check handoff status before continuing locally."
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
