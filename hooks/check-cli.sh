#!/usr/bin/env bash
# Start-of-conversation capability check; plugin upgrades may precede CLI upgrades.
set -eu
payload=$(cat 2>/dev/null) || exit 0
message='alis: this plugin requires a newer Alis CLI. Run `alis upgrade`, then restart this coding agent to enable all Alis hooks.'
shape=ephemeral
if command -v jq >/dev/null 2>&1; then
  if printf '%s' "$payload" | jq -e '.hookEventName == "SessionStart"' >/dev/null 2>&1; then
    shape=system
  else
    # PreInvocation repeats before every model call: speak only at the first
    # one, and not at all when SessionStart already ran for this conversation.
    printf '%s' "$payload" | jq -e '(.invocationNum // 1) <= 1' >/dev/null 2>&1 || exit 0
    conv="$(printf '%s' "$payload" | jq -r '(.conversationId // "") | select(type == "string" and test("^[A-Za-z0-9_-]{1,128}$"))' 2>/dev/null || true)"
    if [ -n "$conv" ] && [ -e "${XDG_CACHE_HOME:-$HOME/.cache}/alis/antigravity/$conv.started" ]; then exit 0; fi
  fi
fi
if alis hooks capabilities 2>/dev/null | grep -qE '"protocol"[[:space:]]*:[[:space:]]*1([,}[:space:]])'; then
  exit 0
fi
if [ "$shape" = system ]; then
  printf '{"injectSteps":[{"systemMessage":{"systemMessage":"%s"}}]}\n' "$message"
else
  printf '{"injectSteps":[{"ephemeralMessage":"%s"}]}\n' "$message"
fi
