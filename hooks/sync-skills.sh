#!/usr/bin/env bash
# Refresh catalog metadata on the first invocation. --cache-only is explicit
# for older CLIs; never fall back to sync without it or install native skills.
# Detach with every stream redirected so the hook cannot wait on the child.
set -euo pipefail
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$hook_dir/common.sh"
first_invocation || noop
command -v alis >/dev/null 2>&1 || noop
(alis skills sync --cache-only --harness antigravity </dev/null >/dev/null 2>&1 &)
noop
