#!/usr/bin/env bash
# Consolidated SessionStart hook:
#   1. Checks CLI hook protocol support (emits an upgrade notice only if outdated).
#   2. Detaches a background catalogue refresh (`alis skills sync --cache-only`).
#   3. Injects concise service workspace pointers for mounted alis.build folders
#      (and the full DBD primer only when ALIS_PRIMER=full; the always_on rule
#      rules/alis-build.md + model_decision topic rules cover normal sessions).
# Emits at most ONE systemMessage, or nothing when there is nothing to say.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"

# Detach catalogue refresh and prune stale per-conversation cache markers (>7d).
if command -v alis >/dev/null 2>&1; then
  (alis skills sync --cache-only --harness antigravity </dev/null >/dev/null 2>&1 &)
fi
if [ -d "$state_dir" ]; then
  (find "$state_dir" -maxdepth 1 \( -name '*.started' -o -name '*.prompt' \) -mtime +7 -delete </dev/null >/dev/null 2>&1 &)
fi

sections=()

# 1. CLI capability check (silent when CLI supports protocol 1).
if ! alis hooks capabilities 2>/dev/null | grep -qE '"protocol"[[:space:]]*:[[:space:]]*1([,}[:space:]])'; then
  sections+=('alis: this plugin requires a newer Alis CLI. Run `alis upgrade`, then restart this coding agent to enable all Alis hooks.')
fi

# 2. Concise service workspace pointers for any mounted alis.build folders.
service_context() {
  local dir="$1" root rest org side s relpath definedir builddir pkg f
  local parts=() segs=() svc=() found_version=0
  case "$dir" in */alis.build/*) ;; *) return 0 ;; esac
  root="${dir%%/alis.build/*}/alis.build"
  rest="${dir#*/alis.build/}"
  IFS='/' read -ra parts <<< "$rest"
  org="${parts[0]:-}"; side="${parts[1]:-}"
  [ -n "$org" ] || return 0
  case "$side" in
    build) segs=("${parts[@]:2}") ;;
    define)
      [ "${parts[2]:-}" = "$org" ] || return 0
      segs=("${parts[@]:3}")
      ;;
    *) return 0 ;;
  esac
  # Stop at the service version, even when the workspace is infra/ or a
  # hidden .playground/ subdirectory. Empty arrays must work on macOS bash 3.2.
  for s in ${segs[@]+"${segs[@]}"}; do
    [ -n "$s" ] || continue
    case "$s" in .|..) return 0 ;; esac
    svc+=("$s")
    if [[ "$s" =~ ^v[0-9]+$ ]]; then found_version=1; break; fi
  done
  [ "${#svc[@]}" -gt 0 ] || return 0
  relpath="$(IFS=/; printf '%s' "${svc[*]}")"
  definedir="$root/$org/define/$org/$relpath"
  builddir="$root/$org/build/$relpath"
  pkg=""
  if [ "$found_version" -eq 1 ]; then
    pkg="$org.$(IFS=.; printf '%s' "${svc[*]}")"
  fi

  printf 'Alis Build workspace: %s\n' "$dir"
  [ -z "$pkg" ] || printf '  Package ID: %s\n' "$pkg"
  if [ "$side" = build ]; then
    printf '  Service implementation (DBD Build).\n'
    if [ -d "$definedir" ]; then
      printf '  Protobuf definitions (DBD Define): %s\n' "$definedir"
    else
      printf '  Expected definitions at %s (not found on disk).\n' "$definedir"
    fi
  else
    printf '  Protobuf API contract (DBD Define).\n'
    if [ -d "$builddir" ]; then
      printf '  Service implementation (DBD Build): %s\n' "$builddir"
    else
      printf '  This contract has no corresponding build/ implementation directory yet.\n'
    fi
  fi
  for f in "$definedir"/*.proto; do
    [ ! -f "$f" ] || printf '  Proto file: %s\n' "${f##*/}"
  done
  return 0
}

svc_ctx="$(while IFS= read -r dir; do service_context "$dir"; done < <(workspaces))"
if [ -n "$svc_ctx" ]; then
  sections+=("$svc_ctx")
fi

# 3. Full DBD primer is opt-in (ALIS_PRIMER=full); rules/alis-build.md is always_on.
if [ "${ALIS_PRIMER:-}" = "full" ]; then
  primer_file="$hook_dir/../context/dbd-primer.md"
  if [ -r "$primer_file" ]; then
    primer_ctx="$(cat "$primer_file" 2>/dev/null || true)"
    [ -z "$primer_ctx" ] || sections+=("$primer_ctx")
  fi
fi

[ "${#sections[@]}" -gt 0 ] || noop

combined=""
for sec in "${sections[@]}"; do
  if [ -z "$combined" ]; then
    combined="$sec"
  else
    combined="${combined}"$'\n\n'"${sec}"
  fi
done
emit_system "$combined"
