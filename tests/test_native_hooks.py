#!/usr/bin/env python3
"""Plugin launch contracts. Python is a development test runner only.
Set ALIS_TEST_CLI to a freshly built CLI to exercise the real native handlers.
The hook subprocess PATH deliberately contains no Python interpreter.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / 'plugins/alis-build').exists():
    HARNESS, HOOKS = 'claude', ROOT / 'plugins/alis-build/hooks'
elif (ROOT / 'plugin.json').exists():
    HARNESS, HOOKS = 'antigravity', ROOT / 'hooks'
elif (ROOT / '.cursor-plugin').exists():
    HARNESS, HOOKS = 'cursor', ROOT / 'plugins/tools/hooks'
else:
    HARNESS, HOOKS = 'codex', ROOT / 'plugins/tools/hooks'
BASH = shutil.which('bash')

class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='alis native hooks ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / 'bin'; self.bin.mkdir()
        for name in ('bash', 'dirname', 'cat', 'grep', 'jq', 'sed', 'tr', 'find'):
            source = shutil.which(name)
            if source:
                (self.bin / name).symlink_to(source)
        self.env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PATH=str(self.bin))
        self.env.pop('ALIS_HANDOFF_ID', None)
        self.env.pop('ALIS_DEV', None)
        for name in ('ALIS_BUILD_SHELL','ALIS_BUILD_WORKSTATION','GOOGLE_CLOUD_WORKSTATIONS','REFRESH_TOKEN_PATH'):
            self.env.pop(name, None)

    def fake(self, body):
        file = self.bin / 'alis'
        file.write_text('#!/bin/sh\n' + body)
        file.chmod(0o755)

    def invoke(self, filename, payload=None, event='PreToolUse'):
        argv = [BASH, str(HOOKS / filename)]
        if filename == 'handoff.sh' and HARNESS == 'antigravity': argv.append(event)
        result = subprocess.run(argv, input=json.dumps(payload or {}), text=True,
                                capture_output=True, env=self.env, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout.strip()

    def claim(self, sid='abc'):
        key = sid if HARNESS == 'claude' else HARNESS + '--' + sid
        path = self.home / '.alis/handoff-sessions' / (key + '.claim')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}')

class NativeHookTests(HookCase):
    def test_no_shipped_python_runtime(self):
        self.assertEqual(list(HOOKS.glob('*.py')), [])
        self.assertFalse((HOOKS / 'run-python.sh').exists())

    def test_optional_hooks_forward_payload_and_native_response(self):
        handlers = {'warn-secrets.sh':'secrets'} if HARNESS != 'antigravity' else {}
        if HARNESS == 'claude': handlers.update({'allow-alis-cli.sh':'permission', 'sync-skills.sh':'sync'})
        self.fake('printf "%s\\n" "$@" > "$HOME/argv"\ncat > "$HOME/input"\nprintf \'%s\\n\' \'{"native":true}\'\n')
        payload = {'session_id':'session-a', 'tool_input':{'command':'echo "literal $text"'}, 'source':'startup'}
        for filename, handler in handlers.items():
            with self.subTest(handler=handler):
                self.assertEqual(json.loads(self.invoke(filename,payload)), {'native':True})
                self.assertEqual(json.loads((self.home/'input').read_text()), payload)
                args=(self.home/'argv').read_text().splitlines()
                self.assertEqual(args[:4], ['hooks','run','--protocol','1'])
                self.assertEqual(args[args.index('--harness')+1], HARNESS)
                self.assertEqual(args[args.index('--handler')+1], handler)
                self.assertEqual(Path(args[args.index('--plugin-root')+1]).resolve(), HOOKS.parent)

    def test_missing_cli_is_quiet_on_tool_hooks(self):
        if HARNESS != 'antigravity': self.assertEqual(self.invoke('warn-secrets.sh'), '')
        if HARNESS == 'claude': self.assertEqual(self.invoke('allow-alis-cli.sh'), '')

    def test_startup_reports_upgrade_for_older_cli(self):
        self.fake('exit 1\n')
        self.assertIn('alis upgrade', self.invoke('check-cli.sh'))
        self.fake('printf \'%s\\n\' \'{"protocol":1}\'\n')
        self.assertEqual(self.invoke('check-cli.sh'), '')
        self.fake('printf \'%s\\n\' \'{"protocol":10}\'\n')
        self.assertIn('alis upgrade', self.invoke('check-cli.sh'))

    @unittest.skipUnless(os.environ.get('ALIS_TEST_CLI'), 'set ALIS_TEST_CLI for native binary integration')
    def test_real_binary_without_python_on_path(self):
        (self.bin/'alis').symlink_to(Path(os.environ['ALIS_TEST_CLI']).resolve())
        self.assertEqual(self.invoke('check-cli.sh'), '')
        if HARNESS != 'antigravity':
            value='sk_'+'live_'+'FAKE'*6
            p={'session_id':'one','tool_name':'Bash','tool_input':{'command':'cat .env'},'tool_response':{'stdout':value}}
            if HARNESS=='cursor': p.update(conversation_id='one',tool_output=json.dumps({'text':value}))
            answer=json.loads(self.invoke('warn-secrets.sh',p))
            context=answer.get('additional_context') if HARNESS=='cursor' else answer['hookSpecificOutput']['additionalContext']
            self.assertIn('stripe',context);self.assertNotIn(value,json.dumps(answer))
            self.assertEqual(self.invoke('warn-secrets.sh',p),'')
        if HARNESS=='claude':
            p={'permission_mode':'plan','tool_input':{'command':'alis deploy example.app.api.v1'}}
            self.assertEqual(json.loads(self.invoke('allow-alis-cli.sh',p))['hookSpecificOutput']['permissionDecision'],'deny')
            p.update(alis_module='cli')
            self.assertEqual(self.invoke('allow-alis-cli.sh',p),'')

@unittest.skipIf(HARNESS=='cursor','Cursor has no handoff hook')
class NativeHandoffTests(HookCase):
    def test_native_cli_gets_original_payload(self):
        self.fake('printf "%s\\n" "$@" > "$HOME/argv"\ncat > "$HOME/input"\nprintf \'%s\\n\' \'{"decision":"native"}\'\n')
        p={'session_id':'abc','hook_event_name':'PreToolUse','tool_input':{'text':'$literal'}}
        self.assertEqual(json.loads(self.invoke('handoff.sh',p)),{'decision':'native'})
        self.assertEqual(json.loads((self.home/'input').read_text()),p)
        self.assertEqual((self.home/'argv').read_text().splitlines()[:2],['hooks','run'])

    def test_legacy_coordinator_still_fences(self):
        self.fake('case "$1" in hooks) exit 1 ;; esac\ncat > "$HOME/legacy"\nprintf \'%s\\n\' \'{"continue":false,"stopReason":"claimed"}\'\n')
        p={'session_id':'abc','hook_event_name':'PreToolUse'}
        out=json.loads(self.invoke('handoff.sh',p))
        if HARNESS=='antigravity': self.assertEqual(out,{'decision':'deny','reason':'claimed'})
        elif HARNESS=='codex': self.assertEqual(out['hookSpecificOutput']['permissionDecision'],'deny')
        else: self.assertEqual(out['continue'],False)
        old=json.loads((self.home/'legacy').read_text())
        if HARNESS!='claude': self.assertEqual((old['agent'],old['integration']),(HARNESS,2))

    def test_unavailable_cli_preserves_claim(self):
        self.fake('exit 1\n')
        p={'session_id':'abc','hook_event_name':'PreToolUse'}
        self.assertEqual(self.invoke('handoff.sh',p),'')
        self.claim()
        answer=json.loads(self.invoke('handoff.sh',p))
        if HARNESS=='antigravity': self.assertEqual(answer['decision'],'deny')
        else: self.assertEqual(answer['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertEqual(self.invoke('handoff.sh',dict(p,session_id='../abc')),'')
        self.assertEqual(self.invoke('handoff.sh',dict(p,session_id='abc\n')),'')

    def test_unavailable_cli_and_jq_preserve_claim(self):
        if HARNESS=='claude': self.skipTest('Claude fallback already uses no jq')
        self.fake('exit 1\n');self.claim()
        (self.bin/'jq').unlink(missing_ok=True)
        output=self.invoke('handoff.sh',{'session_id':'abc','hook_event_name':'PreToolUse'})
        self.assertTrue(output)

if __name__=='__main__': unittest.main()
