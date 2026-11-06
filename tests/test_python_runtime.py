"""Exercise shipped hook commands with Windows-style Python aliases."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "plugin.json").exists():
    AGENT, HOOKS = "antigravity", ROOT / "hooks"
elif (ROOT / ".agents").exists():
    AGENT, HOOKS = "codex", ROOT / "plugins/tools/hooks"
else:
    AGENT, HOOKS = "cursor", ROOT / "plugins/tools/hooks"


class PythonRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="alis python ")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        for name in ("bash", "cat", "dirname", "grep", "jq"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.hooks = self.home / "plugin with spaces" / "hooks"
        shutil.copytree(HOOKS, self.hooks, ignore=shutil.ignore_patterns("__pycache__"))
        if AGENT == "antigravity":
            shutil.copy(ROOT / "hooks.json", self.hooks.parent / "hooks.json")
        self.log = self.home / "python-calls"
        self.receipt = self.home / "handoff-payload"
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                        ALIS_TEST_LOG=str(self.log), ALIS_TEST_RECEIPT=str(self.receipt),
                        PYTHONDONTWRITEBYTECODE="1")
        self.write_executable("alis", '#!/bin/bash\ncat > "$ALIS_TEST_RECEIPT"\nprintf "{}\\n"\n')

    def write_executable(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def candidate(self, name, kind="working"):
        body = '#!/bin/bash\nprintf "%s\\n" "$0 $*" >> "$ALIS_TEST_LOG"\n'
        if name == "py":
            body += '[ "$1" = "-3" ] || exit 99\nshift\n'
        if kind == "alias":
            body += 'echo "Python was not found; install from the Microsoft Store" >&2\nexit 9009\n'
        elif kind == "old":
            body += ('exec ' + shlex.quote(sys.executable) +
                     ' -c \'import sys; sys.version_info = (3, 8); exec(sys.argv[1])\' "$2"\n')
        else:
            body += 'exec ' + shlex.quote(sys.executable) + ' "$@"\n'
        self.write_executable(name, body)

    def run_script(self, name, payload, *args):
        return subprocess.run([str(self.bin / "bash"), str(self.hooks / name), *args],
                              input=json.dumps(payload), capture_output=True, text=True,
                              cwd=self.hooks.parent, env=self.env, timeout=10)

    def run_handoff(self, event="PreToolUse", sid="session"):
        payload = {"hook_event_name": event, "fullyIdle": False,
                   "workspacePaths": ["/workspace with spaces"], "background_tasks": ["task-1"]}
        payload["conversationId" if AGENT == "antigravity" else "session_id"] = sid
        if AGENT == "antigravity":
            config = json.loads((self.hooks.parent / "hooks.json").read_text())
            entry = config["alis-handoff"][event][0]
            command = entry.get("command") or entry["hooks"][0]["command"]
            return subprocess.run(shlex.split(command), input=json.dumps(payload),
                                  capture_output=True, text=True, cwd=self.hooks.parent,
                                  env=self.env, timeout=10)
        return self.run_script("handoff.sh", payload)

    def run_warning(self):
        if AGENT == "cursor":
            payload = {"tool_name": "read_file", "tool_output": '{"text":"https://example.test"}'}
        else:
            payload = {"hook_event_name": "PostToolUse", "tool_name": "Read",
                       "tool_response": {"content": "https://example.test"}}
        return self.run_script("warn-secrets.sh", payload)

    def run_entrypoints(self):
        cases = []
        if AGENT != "antigravity":
            cases.append(("secrets-hook.py", self.run_warning))
        if AGENT != "cursor":
            cases.append(("handoff.py", self.run_handoff))
        for script, run in cases:
            self.log.write_text("")
            result = run()
            yield script, result

    def assert_working(self, selected):
        for script, result in self.run_entrypoints():
            with self.subTest(script=script):
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                executions = [line for line in self.log.read_text().splitlines()
                              if "/hooks/" + script in line]
                self.assertEqual(len(executions), 1)
                self.assertTrue(executions[0].startswith(str(self.bin / selected) + " "))
                if script == "handoff.py":
                    received = json.loads(self.receipt.read_text())
                    self.assertEqual(received["agent"], AGENT)
                    self.assertEqual(received["integration"], 2)
                    self.assertEqual(received["background_tasks"], ["task-1"])
                    self.assertEqual(received["workspacePaths"], ["/workspace with spaces"])
                    self.assertIs(received["fullyIdle"], False)

    def test_alias_falls_back_to_python(self):
        self.candidate("python3", "alias")
        self.candidate("python")
        self.assert_working("python")

    def test_launcher_fallback(self):
        self.candidate("python3", "alias")
        self.candidate("python", "alias")
        self.candidate("py")
        self.assert_working("py")

    def test_working_python3_is_preferred(self):
        for name in ("python3", "python", "py"):
            self.candidate(name)
        self.assert_working("python3")
        self.assertNotIn(str(self.bin / "python") + " ", self.log.read_text())
        self.assertNotIn(str(self.bin / "py") + " ", self.log.read_text())

    def test_unsupported_version_falls_back(self):
        self.candidate("python3", "old")
        self.candidate("python")
        self.assert_working("python")

    def test_only_aliases_are_silent_without_claim(self):
        for name in ("python3", "python", "py"):
            self.candidate(name, "alias")
        for script, result in self.run_entrypoints():
            with self.subTest(script=script):
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_missing_python_is_silent_without_claim(self):
        for script, result in self.run_entrypoints():
            with self.subTest(script=script):
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def claim(self, sid="session"):
        claim = self.home / ".alis/handoff-sessions" / (AGENT + "--" + sid + ".claim")
        claim.parent.mkdir(parents=True, exist_ok=True)
        claim.write_text("{}")

    @unittest.skipIf(AGENT == "cursor", "Cursor has no automatic handoff")
    def test_claimed_session_stays_blocked_without_python(self):
        self.claim()
        for name in ("python3", "python", "py"):
            self.candidate(name, "alias")
        for event in ("PreToolUse", "Stop", "PreInvocation" if AGENT == "antigravity" else "UserPromptSubmit"):
            with self.subTest(event=event):
                result = self.run_handoff(event)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                out = json.loads(result.stdout)
                if AGENT == "codex" and event == "PreToolUse":
                    self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
                elif AGENT == "codex":
                    self.assertIs(out["continue"], False)
                elif event == "PreToolUse":
                    self.assertEqual(out["decision"], "deny")
                elif event == "PreInvocation":
                    self.assertIn("ephemeralMessage", out["injectSteps"][0])
                else:
                    self.assertEqual(out["decision"], "stop")

    @unittest.skipIf(AGENT == "cursor", "Cursor has no automatic handoff")
    def test_working_runtime_preserves_coordinator_denial(self):
        self.candidate("python3", "alias")
        self.candidate("python")
        self.write_executable("alis", '#!/bin/bash\ncat > "$ALIS_TEST_RECEIPT"\nprintf \'{"continue":false,"stopReason":"handoff owns this session"}\\n\'\n')
        result = self.run_handoff()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        out = json.loads(result.stdout)
        if AGENT == "codex":
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        else:
            self.assertEqual(out["decision"], "deny")

    @unittest.skipIf(AGENT == "cursor", "Cursor has no automatic handoff")
    def test_unrelated_or_invalid_session_does_not_read_claim(self):
        self.claim()
        for sid in ("other", "../session", "session\n", {"invalid": "session"}):
            result = self.run_handoff(sid=sid)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    @unittest.skipIf(AGENT == "cursor", "Cursor has no automatic handoff")
    def test_missing_json_parser_does_not_bypass_claim(self):
        self.claim()
        (self.bin / "jq").unlink()
        result = self.run_handoff()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        out = json.loads(result.stdout)
        if AGENT == "codex":
            self.assertIs(out["continue"], False)
        else:
            self.assertEqual(out["decision"], "deny")

    @unittest.skipIf(AGENT != "antigravity", "Antigravity manifest event routing")
    def test_every_registered_handoff_event_uses_working_runtime(self):
        self.candidate("python3", "alias")
        self.candidate("python")
        for event in ("PreInvocation", "PostInvocation", "PreToolUse", "PostToolUse", "Stop"):
            result = self.run_handoff(event)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertEqual(json.loads(self.receipt.read_text())["hook_event_name"], event)

    def test_probe_preserves_stdin_and_arguments(self):
        self.candidate("python")
        script = self.home / "echo payload.py"
        script.write_text("import json, sys\nprint(json.dumps([sys.argv[1:], json.load(sys.stdin)]))\n")
        payload = {"text": "spaces and ünicode"}
        result = self.run_script("run-python.sh", payload, str(script), "argument with spaces")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(json.loads(result.stdout), [["argument with spaces"], payload])

    def test_real_script_failures_are_preserved(self):
        self.candidate("python3")
        script = self.home / "failed.py"
        script.write_text("import sys\nprint('hook failed', file=sys.stderr)\nsys.exit(7)\n")
        result = self.run_script("run-python.sh", {}, str(script))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, "", "hook failed\n"))


if __name__ == "__main__":
    unittest.main()
