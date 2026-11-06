#!/usr/bin/env bash
# Startup-only capability check; plugin upgrades may precede CLI upgrades.
set -eu
# PreInvocation repeats within a session; show compatibility guidance only on its first invocation.
payload=$(cat 2>/dev/null) || exit 0
if command -v jq >/dev/null 2>&1; then
  printf '%s' "$payload" | jq -e '(.invocationNum // 1) <= 1' >/dev/null 2>&1 || exit 0
fi
if alis hooks capabilities 2>/dev/null | grep -qE '"protocol"[[:space:]]*:[[:space:]]*1([,}[:space:]])'; then
  exit 0
fi
printf '%s\n' '{"injectSteps":[{"ephemeralMessage":"alis: this plugin requires a newer Alis CLI. Run `alis upgrade`, then restart this coding agent to enable all Alis hooks."}]}'
