import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
HOOK=ROOT/'hooks/handoff.py'
if not HOOK.exists(): HOOK=ROOT/'plugins/tools/hooks/handoff.py'
spec=importlib.util.spec_from_file_location('alis_handoff_hook',HOOK)
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)

class HandoffBridgeTests(unittest.TestCase):
 def test_vendor_fences(self):
  response={'continue':False,'stopReason':'handoff'}
  self.assertEqual(hook.output('codex','PreToolUse',response)['hookSpecificOutput']['permissionDecision'],'deny')
  self.assertEqual(hook.output('antigravity','PreToolUse',response)['decision'],'deny')
  self.assertEqual(hook.output('antigravity','PostInvocation',response)['terminationBehavior'],'terminate')
  self.assertIn('injectSteps',hook.output('antigravity','PreInvocation',response))
 def test_lifecycle_payload_keeps_native_inventory(self):
  payload={'conversationId':'session','fullyIdle':False}
  with patch.object(sys,'argv',['hook','antigravity','Stop']),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))),patch.object(hook.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{}')) as run:
   hook.main()
  sent=json.loads(run.call_args.kwargs['input'])
  self.assertIs(sent['fullyIdle'],False);self.assertEqual(sent['integration'],2);self.assertEqual(sent['hook_event_name'],'Stop')
 def test_failed_coordinator_fences_claimed_session(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'.alis/handoff-sessions/codex--session.claim';path.parent.mkdir(parents=True);path.write_text('{}')
   output=io.StringIO()
   with patch.object(sys,'argv',['hook','codex']),patch.object(sys,'stdin',io.StringIO('{"session_id":"session","hook_event_name":"PreToolUse"}')),patch.object(sys,'stdout',output),patch.object(hook.Path,'home',return_value=Path(tmp)),patch.object(hook.subprocess,'run',side_effect=OSError('unavailable')):
    hook.main()
   self.assertEqual(json.loads(output.getvalue())['hookSpecificOutput']['permissionDecision'],'deny')

if __name__=='__main__':unittest.main()
