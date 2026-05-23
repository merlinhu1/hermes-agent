"""Minimal gateway /personality picker coverage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource


class PickerAdapter:
    def __init__(self):
        self.kwargs = None

    async def send_personality_picker(self, **kwargs):
        self.kwargs = kwargs
        return SendResult(success=True)


def _make_event() -> MessageEvent:
    return MessageEvent(
        text="/personality",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="12345",
            chat_type="dm",
            user_id="user-1",
        ),
        message_id="m1",
    )


@pytest.mark.asyncio
async def test_personality_command_sends_picker_and_selection_reuses_set_path(monkeypatch, tmp_path):
    config = {"agent": {"personalities": {"coder": "Code sharply."}}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: config)

    adapter = PickerAdapter()
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._ephemeral_system_prompt = ""
    runner.config = SimpleNamespace(group_sessions_per_user=True, thread_sessions_per_user=False)
    runner.session_store = SimpleNamespace(
        _generate_session_key=lambda source: "agent:main:telegram:dm:12345"
    )

    response = await runner._handle_personality_command(_make_event())

    assert response is None
    assert adapter.kwargs["chat_id"] == "12345"
    assert [entry["name"] for entry in adapter.kwargs["personalities"]] == ["none", "coder"]
    assert adapter.kwargs["current_personality"] == "none"

    await adapter.kwargs["on_personality_selected"]("12345", "coder")

    assert runner._ephemeral_system_prompt == "Code sharply."
    saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert saved["agent"]["system_prompt"] == "Code sharply."
