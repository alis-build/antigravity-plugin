#!/usr/bin/env bash
# Validate the Alis Build Antigravity plugin before release.
#
# Checks:
#   1. Plugin manifests and native hooks.json are valid JSON (jq).
#   2. Their versions match.
#   3. Every shell script parses (bash -n).
#   4. Every skills/*/SKILL.md has name + description frontmatter.
#   5. No unsubstituted double-underscore placeholder tokens anywhere.
#   6. No Google-MCP material anywhere (the canonical Claude plugin dropped
#      it; it must not reappear here).
#   7. policies/*.toml parse as TOML (soft check, needs python3 with tomllib).
#   8. Native hook behavior and compatibility primer consistency (python3).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }
ok() { echo "ok: $*"; }

command -v jq >/dev/null 2>&1 || { echo "validate.sh requires jq" >&2; exit 1; }

# 1. JSON validity.
for f in plugin.json gemini-extension.json hooks.json; do
  if jq -e . "$root/$f" >/dev/null 2>&1; then
    ok "$f is valid JSON"
  else
    err "$f is not valid JSON"
  fi
done

# 2. Versions match.
pv="$(jq -r '.version // empty' "$root/plugin.json" 2>/dev/null || true)"
ev="$(jq -r '.version // empty' "$root/gemini-extension.json" 2>/dev/null || true)"
if [ -n "$pv" ] && [ "$pv" = "$ev" ]; then
  ok "versions match ($pv)"
else
  err "version mismatch: plugin.json='$pv' gemini-extension.json='$ev'"
fi

# 3. Shell scripts parse.
while IFS= read -r -d '' script; do
  if bash -n "$script" 2>/dev/null; then
    ok "bash -n ${script#"$root"/}"
  else
    err "bash -n failed: ${script#"$root"/}"
  fi
done < <(find "$root" -name '*.sh' -not -path '*/.git/*' -print0)

# 4. Skill frontmatter.
found_skill=0
while IFS= read -r -d '' skill; do
  found_skill=1
  rel="${skill#"$root"/}"
  head -1 "$skill" | grep -q '^---$' || err "$rel does not start with frontmatter"
  fm="$(awk '/^---$/{n++; next} n==1{print} n>=2{exit}' "$skill")"
  echo "$fm" | grep -q '^name:' || err "$rel frontmatter missing name"
  echo "$fm" | grep -q '^description:' || err "$rel frontmatter missing description"
  ok "$rel has name + description frontmatter"
done < <(find "$root/skills" -mindepth 2 -maxdepth 2 -name 'SKILL.md' -print0)
[ "$found_skill" -eq 1 ] || err "no skills/*/SKILL.md found"

# 5. Unsubstituted placeholders. Pattern assembled so this script never
# matches itself.
u='_'
placeholder="${u}${u}[A-Za-z0-9_]+${u}${u}"
if hits="$(grep -rInE "$placeholder" "$root" --exclude-dir=.git 2>/dev/null)"; then
  err "unsubstituted placeholders found:"$'\n'"$hits"
else
  ok "no unsubstituted placeholders"
fi

# 6. Forbidden strings (assembled at runtime so this script never matches
# itself): the retired Google-MCP material.
c1="connect"; c2="google"; d1="developer"; d2="knowledge"; D1="Developer"; D2="Knowledge"
forbidden=("${c1}-${c2}" "${d1}${d2}" "${D1} ${D2}")
for s in "${forbidden[@]}"; do
  if hits="$(grep -rInF "$s" "$root" --exclude-dir=.git 2>/dev/null)"; then
    err "forbidden string '$s' found:"$'\n'"$hits"
  else
    ok "no occurrences of '$s'"
  fi
done

# 7. TOML parse (soft: skipped when python3/tomllib is unavailable).
if command -v python3 >/dev/null 2>&1 && python3 -c 'import tomllib' 2>/dev/null; then
  while IFS= read -r -d '' toml; do
    if python3 -c 'import sys, tomllib; tomllib.load(open(sys.argv[1], "rb"))' "$toml" 2>/dev/null; then
      ok "TOML parses: ${toml#"$root"/}"
    else
      err "TOML parse failed: ${toml#"$root"/}"
    fi
  done < <(find "$root/policies" -name '*.toml' -print0 2>/dev/null)
else
  echo "skip: python3 tomllib unavailable, TOML parse not checked"
fi

# 8. Run behavior checks with an isolated HOME and fake CLI.
if command -v python3 >/dev/null 2>&1; then
  if python3 "$root/tests/hooks-test.py"; then
    ok "native hook regression tests"
  else
    err "native hook regression tests failed"
  fi
else
  err "python3 is required for native hook regression tests"
fi

if [ "$fail" -ne 0 ]; then
  echo "validate.sh: FAILED" >&2
  exit 1
fi
echo "validate.sh: all checks passed"
