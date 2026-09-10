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
        for command in ("jq", "bash", "cat", "dirname", "touch"):
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
        return json.loads(result.stdout)

    def context(self, script="load-primer.sh", **kwargs):
        result = self.invoke(script, **kwargs)
        if not result:
            return ""
        self.assertEqual(set(result), {"injectSteps"})
        steps = result["injectSteps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(set(steps[0]), {"ephemeralMessage"})
        return steps[0]["ephemeralMessage"]

    def test_primer_gating(self):
        self.assertIn("# Alis Build — Define, Build, Deploy (DBD)", self.context())
        for invocation in (1, 8):
            with self.subTest(invocation=invocation):
                self.assertIn("# Alis Build — DBD refresher", self.context(payload={
                    "workspacePaths": [str(self.workspace)], "invocationNum": invocation,
                }))
        payload = {"workspacePaths": [str(self.plain)], "invocationNum": 0}
        self.assertEqual(self.context(payload=payload), "")
        self.cli()
        self.assertIn("DBD refresher", self.context(payload=payload))

    def test_primer_overrides(self):
        self.assertEqual(self.context(env={"ALIS_PRIMER": "off"}), "")
        self.assertIn("DBD refresher", self.context(env={"ALIS_PRIMER": "digest"}))
        self.assertIn("Define, Build, Deploy (DBD)", self.context(
            payload={"workspacePaths": [str(self.plain)], "invocationNum": 7},
            env={"ALIS_PRIMER": "full"},
        ))

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
        self.assertIn("Define, Build, Deploy (DBD)", self.context(
            root=copy, env={"ALIS_PRIMER": "digest"},
        ))
        (copy / "context/dbd-primer.md").unlink()
        self.assertEqual(self.context(root=copy), "")

    def test_service_counterparts_and_nested_directories(self):
        for path in (self.workspace, self.workspace / "infra", self.definitions / "nested"):
            with self.subTest(path=path):
                text = self.context("inject-service-context.sh", payload={
                    "workspacePaths": [str(path)],
                })
                self.assertIn("Package id: acme.os.demo.v1", text)
                self.assertIn("Proto file: demo.proto", text)
                counterpart = self.workspace if path.is_relative_to(self.definitions) else self.definitions
                self.assertIn(str(counterpart), text)

    def test_multiple_workspaces_and_deduplication(self):
        text = self.context("inject-service-context.sh", payload={"workspacePaths": [
            str(self.plain), str(self.workspace), str(self.workspace), str(self.definitions),
        ]})
        self.assertEqual(text.count("Package id: acme.os.demo.v1"), 2)

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
        self.assertNotIn("Package id:", text)

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
        ):
            with self.subTest(command=command):
                self.assertEqual(self.approval(command)["decision"], "allow")
        self.assertFalse((self.base / ".alis/agent-approval.json").exists())

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
            "alis docs && alis deploy --confirm-production",
            "alis deploy --confirm-production > /tmp/log",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.approval(command)["decision"], "force_ask")

    def test_optional_subcommand_allowlist(self):
        env = {"ALIS_ALLOWED_SUBCMDS": "define build deploy operations"}
        self.assertEqual(self.approval("alis build --json", env=env)["decision"], "allow")
        self.assertEqual(self.approval("alis docs", env=env), {})
        self.assertEqual(self.approval("alis", env=env), {})
        self.assertEqual(self.approval("alis deploy --confirm-production", env=env)["decision"], "force_ask")

    def test_unrelated_tool_cannot_be_approved(self):
        self.assertEqual(self.invoke("allow-alis-cli.sh", payload={"toolCall": {
            "name": "view_file", "args": {"CommandLine": "alis docs"},
        }}), {})

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

    def test_bad_input_and_missing_jq_are_quiet(self):
        for script in ("load-primer.sh", "inject-service-context.sh", "sync-skills.sh", "allow-alis-cli.sh"):
            for raw in ("", "not json", "[]", "null"):
                with self.subTest(script=script, raw=raw):
                    self.assertEqual(self.invoke(script, raw=raw), {})
        self.bin.joinpath("jq").unlink()
        for script in ("load-primer.sh", "inject-service-context.sh", "sync-skills.sh", "allow-alis-cli.sh"):
            self.assertEqual(self.invoke(script), {})

    def test_manifest_handlers_execute_from_plugin_root(self):
        config = json.loads(ROOT.joinpath("hooks.json").read_text())
        payload = {"invocationNum": 1, "workspacePaths": [str(self.workspace)]}
        for handler in config["alis-build-context"]["PreInvocation"]:
            result = subprocess.run(handler["command"], shell=True, cwd=ROOT,
                                    input=json.dumps(payload), text=True, capture_output=True,
                                    env=self.env, timeout=handler["timeout"])
            self.assertEqual(result.returncode, 0, result.stderr)
            json.loads(result.stdout)
        group = config["alis-build-cli"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "run_command")
        self.assertTrue(ROOT.joinpath(group["hooks"][0]["command"].split()[-1]).is_file())

    def test_compatibility_primer_stays_in_sync(self):
        gemini = ROOT.joinpath("GEMINI.md").read_text().split("\n---\n\n", 1)[1]
        self.assertEqual(gemini, ROOT.joinpath("context/dbd-primer.md").read_text())


unittest.main(verbosity=2)
