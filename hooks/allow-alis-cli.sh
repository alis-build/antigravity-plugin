#!/usr/bin/env bash
# Native PreToolUse permission decisions. Deliberately do not manufacture a
# Claude agent-approval.json: Antigravity provides no equivalent permission_mode.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"
cmd="$(printf '%s' "$payload" | jq -r '
  select(.toolCall.name == "run_command") |
  .toolCall.args.CommandLine | select(type == "string")
' 2>/dev/null)" || noop
[ -n "$cmd" ] || noop

force_ask() {
  jq -nc '{decision: "force_ask", reason: "This alis command requires explicit human approval."}'
  exit 0
}

# Check approval flags before the simple-command filter, so a chained command
# carrying a human-approval flag still prompts even with cached permissions.
case "$cmd" in
  *--confirm-production*|*--approve*) force_ask ;;
esac
if [[ "$cmd" =~ alis[[:blank:]]+blocks?[[:blank:]] ]] &&
   [[ "$cmd" == *uninstall* ]] && [[ "$cmd" == *--yes* ]]; then
  force_ask
fi

# Conservative whitelist: no expansion, globbing, escapes, chaining,
# redirects, comments or control characters, even inside quotes.
[[ "$cmd" =~ ^[a-zA-Z0-9\ ._:/@=+,\"\'-]+$ ]] || noop
read -r first sub rest <<< "$cmd"
[ "$first" = alis ] || noop
if [ -n "${ALIS_ALLOWED_SUBCMDS:-}" ]; then
  allowed=0
  for s in $ALIS_ALLOWED_SUBCMDS; do
    if [ "$s" = "$sub" ]; then allowed=1; break; fi
  done
  [ "$allowed" -eq 1 ] || noop
fi
jq -nc '{decision: "allow", reason: "Auto-approved alis CLI command (Alis Build plugin)."}'
