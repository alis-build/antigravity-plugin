#!/usr/bin/env bash
# Full DBD primer on the first workspace invocation; a transient digest on
# later invocations. Outside alis.build, inject a digest only if alis exists.
# ALIS_PRIMER=full|digest|off overrides selection on every invocation.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"

want=digest
case "${ALIS_PRIMER:-}" in
  off) noop ;;
  full|digest) want="$ALIS_PRIMER" ;;
  *)
    in_workspace=0
    while IFS= read -r dir; do
      case "$dir" in */alis.build/*|*/alis.build) in_workspace=1 ;; esac
    done < <(workspaces)
    if [ "$in_workspace" -eq 1 ]; then
      if first_invocation; then want=full; fi
    else
      command -v alis >/dev/null 2>&1 || noop
    fi
    ;;
esac

primer="$hook_dir/../context/dbd-primer.md"
digest="$hook_dir/../context/dbd-digest.md"
file="$primer"
if [ "$want" = digest ] && [ -r "$digest" ]; then file="$digest"; fi
[ -r "$file" ] || noop
context="$(cat "$file" 2>/dev/null)" || noop
emit_context "$context"
