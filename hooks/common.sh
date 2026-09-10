#!/usr/bin/env bash
# Sourced by native Antigravity hooks. Hook cwd is the plugin root, not the
# user's workspace; use workspacePaths from stdin for all workspace context.

noop() { printf '{}\n'; exit 0; }
command -v jq >/dev/null 2>&1 || noop
payload="$(cat 2>/dev/null)" || noop
printf '%s' "$payload" | jq -e 'type == "object"' >/dev/null 2>&1 || noop

workspaces() {
  printf '%s' "$payload" | jq -r '
    (.workspacePaths // []) | if type == "array" then . else [] end |
    map(select(type == "string") | select(startswith("/")) |
        select(test("[\u0000-\u001f]") | not)) | unique[]
  ' 2>/dev/null
}

# Protojson can omit zero-valued fields. Do not infer a Claude source event:
# Antigravity exposes an invocation counter, not startup/resume/compact events.
first_invocation() {
  printf '%s' "$payload" | jq -e '(.invocationNum // 0) == 0' >/dev/null 2>&1
}

emit_context() {
  [ -n "$1" ] || noop
  jq -nc --arg context "$1" '{injectSteps: [{ephemeralMessage: $context}]}'
}
