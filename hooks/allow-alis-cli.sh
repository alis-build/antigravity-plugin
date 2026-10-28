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
      jq -n '{decision: "allow", reason: "Auto-approved workspace file access within the same build environment (Alis Build plugin)."}'
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
jq -n '{decision: "allow", reason: "Auto-approved alis CLI command (Alis Build plugin)."}'
