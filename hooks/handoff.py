#!/usr/bin/env python3
"""Small lifecycle bridge; all ownership and inventory logic lives in alis."""
import json
from pathlib import Path
import re
import subprocess
import sys


def output(agent, event, response):
    if response.get("continue") is not False:
        return {}
    reason = response.get("stopReason", "This session is handing off to a workstation.")
    if agent == "antigravity":
        if event == "PreToolUse":
            return dict(decision="deny", reason=reason)
        if event == "PostInvocation":
            return dict(terminationBehavior="terminate")
        if event == "PreInvocation":
            return dict(injectSteps=[dict(ephemeralMessage=reason)])
        return dict(decision="stop", reason=reason)
    if agent == "codex" and event == "PreToolUse":
        return dict(hookSpecificOutput=dict(hookEventName=event, permissionDecision="deny", permissionDecisionReason=reason))
    return response


def main():
    agent = sys.argv[1]
    payload = json.load(sys.stdin)
    event = sys.argv[2] if len(sys.argv) > 2 else payload.get("hook_event_name", "")
    sid = payload.get("session_id", payload.get("conversationId", ""))
    if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
        return
    payload.update(agent=agent, hook_event_name=event, integration=2)
    try:
        result = subprocess.run(["alis", "workstation", "handoff", "_hook"], input=json.dumps(payload), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8)
        if result.returncode:
            raise ValueError("coordinator unavailable")
        response = json.loads(result.stdout or "{}")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        key = sid if agent == "claude" else agent + "--" + sid
        claim = Path.home() / ".alis/handoff-sessions" / (key + ".claim")
        response = {}
        if claim.exists() and event in ("PreToolUse", "UserPromptSubmit", "PreInvocation", "Stop"):
            response = dict(continue_=False, stopReason="This session has a handoff claim but its coordinator is unavailable. Check handoff status before continuing locally.")
            response["continue"] = response.pop("continue_")
    response = output(agent, event, response)
    if response:
        print(json.dumps(response))


if __name__ == "__main__":
    main()
