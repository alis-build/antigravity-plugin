#!/usr/bin/env bash
# Windows App Execution Aliases pass command -v but cannot run Python.
# Probe without consuming stdin or exposing alias errors. Real script output
# and failures are preserved once a supported interpreter is selected.
set -eu
missing_status=0
if [ "${1:-}" = --required ]; then
  # Handoff callers must check their source claim instead of silently skipping.
  missing_status=69
  shift
fi
probe='import sys; sys.exit(sys.version_info < (3, 9))'
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c "$probe" </dev/null >/dev/null 2>&1; then
    exec "$candidate" -B "$@"
  fi
done
if command -v py >/dev/null 2>&1 \
  && py -3 -c "$probe" </dev/null >/dev/null 2>&1; then
  exec py -3 -B "$@"
fi
exit "$missing_status"
