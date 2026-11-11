#!/usr/bin/env python3
"""Exercise native hook contracts without network or the user's alis state."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv[0]).resolve().parent.parent


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="alis hook test ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for command in ("jq", "bash", "cat", "dirname", "touch", "cksum", "mkdir"):
            self.bin.joinpath(command).symlink_to(shutil.which(command))
        self.env = {
            "HOME": str(self.base),
            "PATH": str(self.bin),
        }
        self.workspace = self.base / "alis.build/acme/build/os/demo/v1"
        self.definitions = self.base / "alis.build/acme/define/acme/os/demo/v1"
        self.workspace.mkdir(parents=True)
        self.definitions.mkdir(parents=True)
        self.definitions.joinpath("demo.proto").touch()
        self.plain = self.base / "plain"
        self.plain.mkdir()

    def cli(self, body="exit 0\n"):
        script = self.bin / "alis"
        script.write_text("#!/bin/sh\n" + body)
        script.chmod(0o755)

    def invoke(self, script, payload=None, env=None, raw=None, root=ROOT):
        if payload is None:
            payload = {"workspacePaths": [str(self.workspace)], "invocationNum": 0}
        result = subprocess.run(
            ["/bin/bash", str(root / "hooks" / script)],
            input=json.dumps(payload) if raw is None else raw,
            text=True, capture_output=True, timeout=3,
            cwd=self.plain, env={**self.env, **(env or {})},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        if not result.stdout:
            return {}
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed, "no-op hooks must emit empty stdout, not {}")
        return parsed

    def context(self, script="load-primer.sh", **kwargs):
        result = self.invoke(script, **kwargs)
        if not result:
            return ""
        self.assertEqual(set(result), {"injectSteps"})
        steps = result["injectSteps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(set(steps[0]), {"ephemeralMessage"})
        return steps[0]["ephemeralMessage"]

    def start(self, script="load-primer.sh", conversation="conv-start", **extra):
        """Runs a hook as SessionStart; returns the system message it leaves, or ""."""
        payload = {"hookEventName": "SessionStart", "conversationId": conversation,
                   "workspacePaths": [str(self.workspace)], **extra.pop("payload", {})}
        result = self.invoke(script, payload=payload, **extra)
        if not result:
            return ""
        self.assertEqual(set(result), {"injectSteps"})
        self.assertEqual(len(result["injectSteps"]), 1)
        self.assertEqual(set(result["injectSteps"][0]), {"systemMessage"})
        self.assertEqual(set(result["injectSteps"][0]["systemMessage"]), {"systemMessage"})
        return result["injectSteps"][0]["systemMessage"]["systemMessage"]

    def test_primer_is_given_once_at_session_start(self):
        # A system message stays for the whole conversation, so it is given once.
        self.assertIn("# Alis Build — Define, Build, Deploy (DBD)", self.start())
        for invocation in (0, 1, 8):
            with self.subTest(invocation=invocation):
                self.assertEqual(self.context(payload={
                    "workspacePaths": [str(self.workspace)], "invocationNum": invocation,
                    "conversationId": "conv-start", "hookEventName": "PreInvocation",
                }), "")
        # Outside a workspace there is no primer; the refresher is a rule.
        self.assertEqual(self.start(conversation="conv-plain", payload={"workspacePaths": [str(self.plain)]}), "")

    def test_primer_without_session_start(self):
        # An Antigravity that never fires SessionStart still gets the primer,
        # before the first model call only.
        self.assertIn("# Alis Build — Define, Build, Deploy (DBD)", self.context())
        for invocation in (1, 8):
            with self.subTest(invocation=invocation):
                self.assertEqual(self.context(payload={
                    "workspacePaths": [str(self.workspace)], "invocationNum": invocation,
                }), "")
        self.cli()
        self.assertEqual(self.context(payload={"workspacePaths": [str(self.plain)], "invocationNum": 0}), "")

    def test_primer_overrides(self):
        for mode in ("off", "digest"):
            self.assertEqual(self.context(env={"ALIS_PRIMER": mode}), "")
            self.assertEqual(self.start(env={"ALIS_PRIMER": mode}), "")
        self.assertIn("Define, Build, Deploy (DBD)", self.start(
            conversation="conv-full", payload={"workspacePaths": [str(self.plain)]}, env={"ALIS_PRIMER": "full"},
        ))

    def test_refresher_rule_stays_in_sync(self):
        rule = ROOT.joinpath("rules/alis-build.md").read_text()
        front, body = rule.split("\n---\n", 1)
        self.assertIn("trigger: always_on", front)
        self.assertEqual(body, ROOT.joinpath("context/dbd-digest.md").read_text())

    def test_service_context_and_sync_move_to_session_start(self):
        self.assertIn("Package ID: acme.os.demo.v1", self.start("inject-service-context.sh"))
        later = {"workspacePaths": [str(self.workspace)], "invocationNum": 3, "conversationId": "conv-start"}
        self.assertEqual(self.context("inject-service-context.sh", payload=later), "")
        # Without SessionStart the pointers are re-injected before every call.
        later["conversationId"] = "conv-legacy"
        self.assertIn("Package ID: acme.os.demo.v1", self.context("inject-service-context.sh", payload=later))
        marker = self.base / "synced"
        self.cli('touch "$TEST_MARKER"\n')
        first = {"workspacePaths": [str(self.workspace)], "invocationNum": 0, "conversationId": "conv-start"}
        self.assertEqual(self.invoke("sync-skills.sh", payload=first, env={"TEST_MARKER": str(marker)}), {})
        self.assertFalse(marker.exists(), "sync ran again after SessionStart had handled the conversation")

    def test_workspace_input_not_hook_cwd(self):
        # Invocation zero may be absent under protojson's default-value omission.
        self.assertIn("Define, Build, Deploy (DBD)", self.context(payload={
            "workspacePaths": [str(self.plain), str(self.workspace)],
        }))
        for paths in ([], None, "invalid", [False, {}, "relative", "/tmp/alis.build-fake/x"]):
            with self.subTest(paths=paths):
                self.assertEqual(self.context(payload={"workspacePaths": paths}), "")

    def test_missing_context_files(self):
        copy = self.base / "plugin copy"
        shutil.copytree(ROOT / "hooks", copy / "hooks")
        (copy / "context").mkdir()
        shutil.copy(ROOT / "context/dbd-primer.md", copy / "context")
        self.assertIn("Define, Build, Deploy (DBD)", self.context(root=copy))
        (copy / "context/dbd-primer.md").unlink()
        self.assertEqual(self.context(root=copy), "")

    def test_service_counterparts_and_nested_directories(self):
        for path in (self.workspace, self.workspace / "infra", self.definitions / "nested"):
            with self.subTest(path=path):
                text = self.context("inject-service-context.sh", payload={
                    "workspacePaths": [str(path)],
                })
                self.assertIn("Package ID: acme.os.demo.v1", text)
                self.assertIn("Proto file: demo.proto", text)
                counterpart = self.workspace if path.is_relative_to(self.definitions) else self.definitions
                self.assertIn(str(counterpart), text)

    def test_multiple_workspaces_and_deduplication(self):
        text = self.context("inject-service-context.sh", payload={"workspacePaths": [
            str(self.plain), str(self.workspace), str(self.workspace), str(self.definitions),
        ]})
        self.assertEqual(text.count("Package ID: acme.os.demo.v1"), 2)

    def test_service_roots_vendored_and_non_workspaces(self):
        for path in (
            self.plain, self.base / "alis.build", self.base / "alis.build/acme/build",
            self.base / "alis.build/acme/define", self.base / "alis.build/acme/define/google/api",
            self.base / "alis.build/acme/other/os/demo/v1",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.context("inject-service-context.sh", payload={
                    "workspacePaths": [str(path)],
                }), "")
        text = self.context("inject-service-context.sh", payload={
            "workspacePaths": [str(self.base / "alis.build/acme/build/os")],
        })
        self.assertIn("Protobuf definitions", text)
        self.assertNotIn("Package ID:", text)

    def test_missing_counterparts(self):
        shutil.rmtree(self.definitions)
        self.assertIn("not found on disk", self.context("inject-service-context.sh"))
        self.assertIn("no corresponding build/", self.context("inject-service-context.sh", payload={
            "workspacePaths": [str(self.base / "alis.build/acme/define/acme/os/new/v1")],
        }))

    def approval(self, command, **kwargs):
        return self.invoke("allow-alis-cli.sh", payload={"toolCall": {
            "name": "run_command", "args": {"CommandLine": command},
        }}, **kwargs)

    def test_simple_cli_approvals(self):
        for command in (
            "alis", "alis docs", "  alis build acme.os.demo.v1 --json --deploy -e dev",
            'alis skills suggest "Pub/Sub event handler" --json', "alis ask 'show builds'",
            'alis ask "why did the build fail (exit 1)?"',
            'alis logs runtime acme.os.demo.v1 -e dev --severity ERROR --contains "panic: [nil]" --json',
            'alis rpc invoke acme.os.demo.v1.Service/Get -d \'{"id": "123", "tags": ["a", "b"]}\' --json',
        ):
            with self.subTest(command=command):
                self.assertEqual(self.approval(command)["decision"], "auto_approve")
        self.assertFalse((self.base / ".alis/agent-approval.json").exists())

    def attributed(self, command, conversation="conv-7", **kwargs):
        return self.invoke("allow-alis-cli.sh", payload={"conversationId": conversation, "toolCall": {
            "name": "run_command", "args": {"CommandLine": command},
        }}, **kwargs)

    def test_commands_carry_the_conversation_and_the_plugin(self):
        version = json.loads(ROOT.joinpath("plugin.json").read_text())["version"]
        tail = f" --session-id conv-7 --client-plugin alis/{version}"
        # A CLI that does not answer `hooks capabilities` gets its command as written.
        self.cli("exit 1\n")
        self.assertEqual(set(self.attributed("alis skills load demo --json")), {"decision", "reason"})
        self.cli('[ "$1 $2" = "hooks capabilities" ] || exit 1\necho \'{"protocol":1}\'\n')
        for command, want in (
            ("alis skills load demo --via hook_hint", "alis skills load demo --via hook_hint" + tail),
            ("  alis build acme.os.demo.v1 --json  ", "  alis build acme.os.demo.v1 --json" + tail),
            ('alis ask "why did it fail?"', 'alis ask "why did it fail?"' + tail),
            ("alis --session-id mine docs", f"alis --session-id mine docs --client-plugin alis/{version}"),
        ):
            with self.subTest(command=command):
                result = self.attributed(command)
                self.assertEqual(result["decision"], "auto_approve")
                self.assertEqual(result["overwrite"], {"CommandLine": want})
        # Left alone: a "--" separator, both flags already there, an unusable conversation id.
        for command, conversation in (
            ("alis rpc invoke x -- --raw", "conv-7"),
            ("alis docs --session-id a --client-plugin b/1", "conv-7"),
        ):
            with self.subTest(command=command):
                self.assertNotIn("overwrite", self.attributed(command, conversation=conversation))
        self.assertEqual(self.attributed("alis docs", conversation="../x")["overwrite"],
                         {"CommandLine": f"alis docs --client-plugin alis/{version}"})
        # A command that must be confirmed is never rewritten.
        self.assertEqual(set(self.attributed("alis deploy x --confirm-production")), {"decision", "reason"})

    def test_topic_rules_are_well_formed(self):
        # model_decision, not glob: agy 1.5.5 never activated a glob rule, from a
        # plugin or a workspace, on reading or editing a matching file.
        rules = sorted(p.name for p in ROOT.joinpath("rules").glob("*.md"))
        self.assertEqual(rules, ["alis-build.md", "alis-dependencies.md", "alis-infra.md",
                                 "alis-playground.md", "alis-protos.md"])
        for name in rules:
            if name == "alis-build.md":
                continue
            front = ROOT.joinpath("rules", name).read_text().split("\n---\n", 1)[0]
            self.assertIn("trigger: model_decision", front)
            self.assertRegex(front, r'description: "Alis Build [^"]+Read this before [^"]+"')
            self.assertLess(ROOT.joinpath("rules", name).stat().st_size, 24 * 1024)

    def test_shell_composition_falls_through(self):
        for command in (
            "echo alis", "alisx build", "/tmp/alis build", "env alis build", "ali's' docs",
            "alis docs && touch /tmp/unsafe", "alis docs; echo unsafe", "alis docs | cat",
            "alis docs > /tmp/output", "alis docs < /tmp/input", "alis docs &",
            "alis docs\necho unsafe", "alis docs\recho unsafe", "alis docs\t&& echo unsafe",
            "alis ask $(id)", "alis ask `id`", 'alis ask "$TOKEN"', "alis ask $'text'",
            "alis ask *.txt", "alis ask ~", "alis ask {a,b}", "alis ask \\text",
            "alis docs # comment", "alis ask (text)", "alis ask [a-z]", "alis ask ?",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.approval(command), {})

    def test_human_approval_flags_always_prompt(self):
        for command in (
            "alis deploy --confirm-production", "alis build --approve=true",
            "alis blocks uninstall demo --yes", "alis block --yes uninstall demo",
            "alis --cwd /tmp/x blocks uninstall demo --yes",
            "alis docs && alis deploy --confirm-production",
            "alis deploy --confirm-production > /tmp/log",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.approval(command)["decision"], "force_ask")

    def test_optional_subcommand_allowlist(self):
        env = {"ALIS_ALLOWED_SUBCMDS": "define build deploy operations"}
        self.assertEqual(self.approval("alis build --json", env=env)["decision"], "auto_approve")
        self.assertEqual(self.approval("alis --cwd /tmp/work build --json", env=env)["decision"], "auto_approve")
        self.assertEqual(self.approval("alis --cwd=/tmp/work --json operations wait op/1", env=env)["decision"], "auto_approve")
        self.assertEqual(self.approval("alis docs", env=env), {})
        self.assertEqual(self.approval("alis --cwd /tmp/work docs", env=env), {})
        self.assertEqual(self.approval("alis", env=env), {})
        self.assertEqual(self.approval("alis deploy --confirm-production", env=env)["decision"], "force_ask")

    def test_unrelated_tool_cannot_be_approved(self):
        self.assertEqual(self.invoke("allow-alis-cli.sh", payload={"toolCall": {
            "name": "view_file", "args": {"CommandLine": "alis docs"},
        }}), {})
        self.assertEqual(self.invoke("allow-alis-cli.sh", payload={
            "workspacePaths": [str(self.workspace)],
            "toolCall": {
                "name": "view_file",
                "args": {"AbsolutePath": str(self.definitions / "demo.proto")},
            },
        })["decision"], "auto_approve")
        self.assertEqual(self.invoke("allow-alis-cli.sh", payload={
            "workspacePaths": [str(self.workspace)],
            "toolCall": {
                "name": "view_file",
                "args": {"AbsolutePath": str(self.base / "alis.build/other/define/x.proto")},
            },
        }), {})
        self.assertEqual(self.invoke("allow-alis-cli.sh", payload={
            "workspacePaths": [str(self.workspace)],
            "toolCall": {
                "name": "view_file",
                "args": {"AbsolutePath": str(self.definitions / "../../secret")},
            },
        }), {})

    def test_sync_is_detached_and_catalog_only(self):
        # The fake CLI blocks on a FIFO after recording its call. The parent
        # hook must return before we release it, without inheriting its pipes.
        calls = self.base / "calls"
        release = self.base / "release"
        os.mkfifo(calls)
        os.mkfifo(release)
        call_fd = os.open(calls, os.O_RDWR | os.O_NONBLOCK)
        release_fd = os.open(release, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, call_fd)
        self.addCleanup(os.close, release_fd)
        self.cli('printf "%s\\n" "$*" > "$TEST_CALLS"\n'
                 'read -r release < "$TEST_RELEASE"\n'
                 'echo "must not reach hook stdout"\nexit 1\n')
        try:
            self.assertEqual(self.invoke("sync-skills.sh", env={
                "TEST_CALLS": str(calls), "TEST_RELEASE": str(release),
            }), {})
            self.assertTrue(select.select([call_fd], [], [], 2)[0], "sync did not start")
            self.assertEqual(os.read(call_fd, 4096).decode().strip(),
                             "skills sync --cache-only --harness antigravity")
        finally:
            os.write(release_fd, b"finish\n")

    def test_later_invocations_skip_sync(self):
        marker = self.base / "unexpected-sync"
        self.cli('touch "$TEST_MARKER"\n')
        self.assertEqual(self.invoke("sync-skills.sh", payload={"invocationNum": 2},
                                     env={"TEST_MARKER": str(marker)}), {})
        self.assertFalse(marker.exists())

    RANKED = ("Skill store match for this request — Alis skill: dbd-add-tracing-grpc-go — Adds tracing.\n"
              "Load with `alis skills load dbd-add-tracing-grpc-go --via hook_hint` if relevant; otherwise ignore this note.")

    def suggest(self, prompt, conversation="conv-1", answer=None, env=None):
        """Runs the suggest hook against a fake CLI; returns (context, the request the CLI got)."""
        seen = self.base / "seen"
        seen.unlink(missing_ok=True)
        self.cli('cat > "$TEST_SEEN"\nprintf "\\n%s\\n" "$*" >> "$TEST_SEEN"\n'
                 'cat <<\'ALIS_ANSWER\'\n' + (self.RANKED if answer is None else answer) + '\nALIS_ANSWER\n')
        payload = {"workspacePaths": [str(self.workspace)], "invocationNum": 1,
                   "conversationId": conversation, "lastUserInput": prompt}
        result = self.invoke("suggest-skills.sh", payload=payload, env={"TEST_SEEN": str(seen), **(env or {})})
        context = ""
        if result:
            # A system message, so the note is still there on a later turn.
            self.assertEqual(set(result), {"injectSteps"})
            self.assertEqual([set(step) for step in result["injectSteps"]], [{"systemMessage"}])
            context = result["injectSteps"][0]["systemMessage"]["systemMessage"]
        return context, (seen.read_text() if seen.exists() else None)

    def test_a_skill_store_match_is_noted_beside_the_prompt(self):
        context, seen = self.suggest("are you able to help with grpc tracing?")
        self.assertEqual(context, self.RANKED + "\nIf you answer without loading it, name the skill in your answer "
                         "so the user knows it exists.")
        request, argv = seen.rstrip("\n").rsplit("\n", 1)
        self.assertEqual(argv, "skills suggest --hook --harness codex")
        self.assertEqual(json.loads(request), {
            "hook_event_name": "UserPromptSubmit", "session_id": "conv-1", "cwd": str(self.workspace),
            "permission_mode": "", "prompt": "are you able to help with grpc tracing?",
        })

    def test_a_local_guess_and_an_empty_answer_are_not_noted(self):
        guess = "Possibly relevant Alis skill: build-your-first-ios-app — Guide builders.\nLoad with `alis skills load <id>` if relevant; otherwise ignore this note."
        context, seen = self.suggest("how are sendgrid templates managed?", answer=guess)
        self.assertEqual(context, "")
        self.assertIsNotNone(seen)
        self.cli("cat >/dev/null\nexit 0\n")
        payload = {"conversationId": "conv-2", "lastUserInput": "rename this variable please"}
        self.assertEqual(self.invoke("suggest-skills.sh", payload=payload), {})
        self.cli("cat >/dev/null\necho 'unknown flag: --hook' >&2\nexit 1\n")
        payload["conversationId"] = "conv-3"
        self.assertEqual(self.invoke("suggest-skills.sh", payload=payload), {})

    def test_a_prompt_is_asked_about_once(self):
        # PreInvocation repeats the most recent prompt on an invocation that is
        # not a new one; only a new prompt, or another conversation, asks again.
        prompt = "are you able to help with grpc tracing?"
        self.assertIsNotNone(self.suggest(prompt)[1])
        self.assertEqual(self.suggest(prompt), ("", None))
        self.assertIsNotNone(self.suggest("and with spanner indexes?")[1])
        self.assertIsNotNone(self.suggest(prompt, conversation="conv-9")[1])

    def test_suggestions_can_be_switched_off_and_need_a_prompt(self):
        self.assertEqual(self.suggest("are you able to help with grpc tracing?", env={"ALIS_SUGGEST_ALWAYS": "0"}), ("", None))
        self.assertEqual(self.suggest(""), ("", None))
        self.assertEqual(self.suggest("help with grpc tracing please", conversation="../../etc"), ("", None))
        self.bin.joinpath("alis").unlink()
        payload = {"conversationId": "conv-4", "lastUserInput": "help with grpc tracing please"}
        self.assertEqual(self.invoke("suggest-skills.sh", payload=payload), {})

    def test_bad_input_and_missing_jq_are_quiet(self):
        for script in ("load-primer.sh", "inject-service-context.sh", "sync-skills.sh", "allow-alis-cli.sh", "suggest-skills.sh"):
            for raw in ("", "not json", "[]", "null"):
                with self.subTest(script=script, raw=raw):
                    self.assertEqual(self.invoke(script, raw=raw), {})
        self.bin.joinpath("jq").unlink()
        for script in ("load-primer.sh", "inject-service-context.sh", "sync-skills.sh", "allow-alis-cli.sh"):
            self.assertEqual(self.invoke(script), {})

    def test_manifest_handlers_execute_from_plugin_root(self):
        config = json.loads(ROOT.joinpath("hooks.json").read_text())
        payload = {"invocationNum": 1, "workspacePaths": [str(self.workspace)]}
        self.assertEqual([h["command"] for h in config["alis-context"]["PreInvocation"]][-1], "bash ./hooks/suggest-skills.sh")
        self.assertNotIn("bash ./hooks/suggest-skills.sh", [h["command"] for h in config["alis-context"]["SessionStart"]])
        for handler in config["alis-context"]["SessionStart"] + config["alis-context"]["PreInvocation"]:
            result = subprocess.run(handler["command"], shell=True, cwd=ROOT,
                                    input=json.dumps(payload), text=True, capture_output=True,
                                    env=self.env, timeout=handler["timeout"])
            self.assertEqual(result.returncode, 0, result.stderr)
            if result.stdout:
                self.assertTrue(json.loads(result.stdout))
        group = config["alis-cli"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "run_command")
        self.assertTrue(ROOT.joinpath(group["hooks"][0]["command"].split()[-1]).is_file())

    def test_compatibility_primer_stays_in_sync(self):
        gemini = ROOT.joinpath("gemini/GEMINI.md").read_text().split("\n---\n\n", 1)[1]
        self.assertEqual(gemini, ROOT.joinpath("context/dbd-primer.md").read_text())


unittest.main(verbosity=2)
