from pathlib import Path

from codeguard.stop_event import StopEvent


class TestStopEvent:
    def test_from_claude_code_stop_payload(self):
        payload = {
            "session_id": "abc123",
            "transcript_path": "/home/example/.claude/projects/example/abc123.jsonl",
            "cwd": "/home/example/project",
            "permission_mode": "default",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Done.",
        }

        event = StopEvent.from_hook_input(payload)

        assert event == StopEvent(cwd=Path("/home/example/project"), permission_mode="default")

    def test_from_codex_stop_payload(self):
        payload = {
            "session_id": "abc123",
            "turn_id": "turn-1",
            "transcript_path": None,
            "cwd": "/home/example/project",
            "hook_event_name": "Stop",
            "model": "gpt-5",
            "permission_mode": "plan",
            "stop_hook_active": False,
            "last_assistant_message": "Done.",
        }

        event = StopEvent.from_hook_input(payload)

        assert event == StopEvent(cwd=Path("/home/example/project"), permission_mode="plan")
