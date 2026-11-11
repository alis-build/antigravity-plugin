#!/usr/bin/env bash
# The full DBD primer, once, at the start of a conversation inside an
# alis.build workspace. The short refresher is a rule (rules/alis-build.md),
# which Antigravity keeps in context itself.
# ALIS_PRIMER=full gives the primer outside a workspace too; off or digest
# gives none.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"

if ! at_session_start; then
  seen_session_start && noop
  first_invocation || noop
fi

case "${ALIS_PRIMER:-}" in
  off|digest) noop ;;
  full) ;;
  *)
    in_workspace=0
    while IFS= read -r dir; do
      case "$dir" in */alis.build/*|*/alis.build) in_workspace=1 ;; esac
    done < <(workspaces)
    [ "$in_workspace" -eq 1 ] || noop
    ;;
esac

file="$hook_dir/../context/dbd-primer.md"
[ -r "$file" ] || noop
context="$(cat "$file" 2>/dev/null)" || noop
emit_context "$context"
