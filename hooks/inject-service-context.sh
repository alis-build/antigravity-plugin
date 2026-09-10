#!/usr/bin/env bash
# Map each mounted Alis build/define folder to its counterpart and package.
# Re-inject transient pointers so they survive context compaction.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"

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
  [ -z "$pkg" ] || printf '  Package id: %s\n' "$pkg"
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
  # Read the version root on both sides, including when mounted below it.
  for f in "$definedir"/*.proto; do
    [ ! -f "$f" ] || printf '  Proto file: %s\n' "${f##*/}"
  done
  return 0
}

context="$(while IFS= read -r dir; do service_context "$dir"; done < <(workspaces))"
emit_context "$context"
