#!/usr/bin/env bash
# Auto-approve safe `alis` CLI invocations and same-org build/define file access
# so Define-Build-Deploy runs without per-command confirmation prompts.
source "$(dirname "$0")/common.sh"

tool=$(jq -r '.toolCall.name // empty' <<<"$payload" 2>/dev/null) || noop

if [ "$tool" != "run_command" ]; then
  case "$tool" in
    view_file|list_dir|grep_search|find_by_name|replace_file_content|write_to_file)
      ok=$(jq -r '
        def org_root:
          capture("^(?<root>.*/alis\\.build/[^/]+)/(build|define)(/|$)") | .root;
        (.toolCall.args // {} | (.AbsolutePath // .DirectoryPath // .SearchPath // .SearchDirectory // .TargetFile // empty)) as $target
        | if ($target | type) != "string" or ($target | length) == 0 or ($target | test("(^|/)\\.\\.(/|$)")) then
            "no"
          else
            ([.workspacePaths // [] | .[]? | select(type == "string") | try org_root catch empty] | unique) as $roots
            | (try ($target | org_root) catch "") as $target_root
            | if $target_root != "" and ($roots | index($target_root)) != null then "yes" else "no" end
          end
      ' <<<"$payload" 2>/dev/null) || noop
      [ "$ok" = "yes" ] || noop
      jq -n '{decision: "auto_approve", reason: "Auto-approved workspace file access within the same build environment (Alis Build plugin)."}'
      exit 0
      ;;
    *)
      noop
      ;;
  esac
fi

cmd=$(jq -r '.toolCall.args.CommandLine // empty' <<<"$payload" 2>/dev/null) || noop

force_ask() {
  jq -n '{decision: "force_ask", reason: "This alis command requires explicit human approval."}'
  exit 0
}

# Never auto-approve production confirmation, approval overrides, or block uninstalls with --yes.
# Checked BEFORE the simple-command filter so chained commands cannot bypass it.
case "$cmd" in
  *--confirm-production*|*--approve*)
    force_ask ;;
esac
if [[ "$cmd" =~ (^|[^a-zA-Z0-9_-])alis[[:space:]].*blocks?([[:space:]]|$) && "$cmd" =~ (^|[[:space:]])uninstall([[:space:]]|$) && "$cmd" == *--yes* ]]; then
  force_ask
fi

# Simple single command only: reject pipes, chaining, redirects, subshells, globs, newlines.
# Balanced single/double-quoted arguments may contain JSON/query punctuation (?()[]{}).
[[ "$cmd" != *$'\n'* && "$cmd" != *$'\r'* ]] || noop
sub=$(jq -r '
  (.toolCall.args.CommandLine // "") as $cmd
  | if ($cmd | contains("\n") or contains("\r")) then
      empty
    elif ($cmd | test("^[a-zA-Z0-9 ._:/@=+,\"'\''?()\\[\\]{}-]+$")) and
         ($cmd | test("^ *alis( +([a-zA-Z0-9._:/@=+,-]+|'\''[^'\'']*'\''|\"[^\"]*\")+)* *$")) then
      ($cmd
        | gsub("'\''[^'\'']*'\''|\"[^\"]*\""; "ARG")
        | [splits(" +") | select(length > 0)]
        | reduce .[1:][] as $tok (
            {skip: false, sub: ""};
            if .sub != "" then .
            elif .skip then .skip = false
            elif ($tok == "--cwd" or $tok == "--session-id" or $tok == "--client-plugin") then .skip = true
            elif ($tok | startswith("-")) then .
            else .sub = $tok
            end
          )
        | "ok:" + .sub)
    else
      empty
    end
' <<<"$payload" 2>/dev/null) || noop
[[ "$sub" == ok:* ]] || noop
sub="${sub#ok:}"

# Optional subcommand whitelist: ALIS_ALLOWED_SUBCMDS="define build deploy"
if [ -n "${ALIS_ALLOWED_SUBCMDS:-}" ]; then
  [ -n "$sub" ] || noop
  case " $ALIS_ALLOWED_SUBCMDS " in
    *" $sub "*) ;;
    *) noop ;;
  esac
fi
# Say who is calling: the conversation, so the CLI can attribute the command
# (and a skill load) to this session, and this plugin with its version. Both
# are global flags that identify the call and grant nothing. They go at the
# end of the command, so a command with a "--" separator is left alone, and so
# is one that already carries them. Only for a CLI known to accept them: one
# that answers `alis hooks capabilities` (the flags are older than that
# command). The answer is remembered so the check runs once.
attributed=""
if [ -e "$state_dir/cli-attributes" ] || {
     alis hooks capabilities >/dev/null 2>&1 &&
     { mkdir -p "$state_dir" && : > "$state_dir/cli-attributes"; } 2>/dev/null; }; then
  plugin="$(jq -r '"\(.name)/\(.version)" | select(test("^[a-z0-9-]+/[0-9A-Za-z.+-]+$"))' \
    "$(dirname "$0")/../plugin.json" 2>/dev/null || true)"
  attributed=$(jq -r --arg plugin "$plugin" '
    (.toolCall.args.CommandLine // "") as $cmd
    | ((.conversationId // "") | if type == "string" and test("^[A-Za-z0-9_-]{1,128}$") then . else "" end) as $conv
    | if ($cmd | test("(^| )--( |$)")) then empty else
        ($cmd | sub(" +$"; ""))
        + (if $conv != "" and ($cmd | test("(^| )--session-id( |=)") | not) then " --session-id " + $conv else "" end)
        + (if $plugin != "" and ($cmd | test("(^| )--client-plugin( |=)") | not) then " --client-plugin " + $plugin else "" end)
      end
  ' <<<"$payload" 2>/dev/null) || attributed=""
fi
reason="Auto-approved alis CLI command (Alis Build plugin)."
if [ -n "$attributed" ] && [ "$attributed" != "$cmd" ]; then
  jq -n --arg reason "$reason" --arg command "$attributed" \
    '{decision: "auto_approve", reason: $reason, overwrite: {CommandLine: $command}}'
else
  jq -n --arg reason "$reason" '{decision: "auto_approve", reason: $reason}'
fi
