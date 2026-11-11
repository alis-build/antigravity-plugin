#!/usr/bin/env bash
# Sourced by native Antigravity hooks. Hook cwd is the plugin root, not the
# user's workspace; use workspacePaths from stdin for all workspace context.

noop() { exit 0; }
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

# Protojson can omit zero-valued fields, so a missing counter is invocation 0.
first_invocation() {
  printf '%s' "$payload" | jq -e '(.invocationNum // 0) == 0' >/dev/null 2>&1
}

# The conversation id, when it is safe to use as a file name; else empty.
conversation() {
  printf '%s' "$payload" | jq -r '
    (.conversationId // "") | select(type == "string" and test("^[A-Za-z0-9_-]{1,128}$"))
  ' 2>/dev/null || true
}

# Small per-conversation notes the hooks leave for each other.
state_dir="${XDG_CACHE_HOME:-$HOME/.cache}/alis/antigravity"

# SessionStart fires once per conversation; PreInvocation fires before every
# model call. Work that belongs to the start of a conversation runs at
# SessionStart and leaves a marker, so the PreInvocation copy of the same hook
# (kept for an Antigravity without SessionStart) knows to stand down.
at_session_start() {
  printf '%s' "$payload" | jq -e '.hookEventName == "SessionStart"' >/dev/null 2>&1 || return 1
  local conv; conv="$(conversation)"
  if [ -n "$conv" ]; then
    { mkdir -p "$state_dir" && : > "$state_dir/$conv.started"; } 2>/dev/null || true
  fi
  return 0
}

seen_session_start() {
  local conv; conv="$(conversation)"
  [ -n "$conv" ] && [ -e "$state_dir/$conv.started" ]
}

# A system message stays in the conversation whichever event leaves it.
emit_system() {
  [ -n "$1" ] || noop
  jq -nc --arg context "$1" '{injectSteps: [{systemMessage: {systemMessage: $context}}]}'
}

# At SessionStart the context is a system message, which stays for the whole
# conversation. Anywhere else it is an ephemeral message, which the model sees
# for that one call only.
emit_context() {
  [ -n "$1" ] || noop
  if printf '%s' "$payload" | jq -e '.hookEventName == "SessionStart"' >/dev/null 2>&1; then
    jq -nc --arg context "$1" '{injectSteps: [{systemMessage: {systemMessage: $context}}]}'
  else
    jq -nc --arg context "$1" '{injectSteps: [{ephemeralMessage: $context}]}'
  fi
}
