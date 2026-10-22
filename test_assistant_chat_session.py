"""
Assistant Chat Session Tests
============================

Regression tests for issue #133: assistant answers were lost when the chat
panel was closed (WebSocket disconnected) while a response was streaming.

Run with: python -m pytest test_assistant_chat_session.py
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from server.routers import assistant_chat as router
from server.services import assistant_chat_session as svc


class TextBlock:
    def __init__(self, text: str):
        self.text = text


class AssistantMessage:
    def __init__(self, text: str):
        self.content = [TextBlock(text)]


class FakeClient:
    async def query(self, message: str) -> None:
        self.last_query = message

    async def __aexit__(self, *args) -> None:
        pass


def _fake_receive(parts: list[str], gate: asyncio.Event | None = None):
    async def receive(client, logger):
        for i, part in enumerate(parts):
            if gate is not None and i == 1:
                await gate.wait()
            yield AssistantMessage(part)
    return receive


def _ready_session(conversation_id: int = 1) -> svc.AssistantChatSession:
    session = svc.AssistantChatSession("proj", Path("/tmp/proj"), conversation_id)
    session.client = FakeClient()  # type: ignore[assignment]
    session._client_entered = True
    session._history_loaded = True
    return session


class ClosingWebSocket:
    """WebSocket stub that fails on the Nth send, like a closed browser tab."""

    def __init__(self, fail_after: int):
        self.sent: list[dict] = []
        self.fail_after = fail_after

    async def send_json(self, data: dict) -> None:
        if len(self.sent) >= self.fail_after:
            raise RuntimeError("WebSocket is closed")
        self.sent.append(data)


def test_response_persisted_when_websocket_disconnects_mid_stream():
    stored: list[tuple[str, str]] = []

    async def run():
        session = _ready_session()
        ws = ClosingWebSocket(fail_after=1)
        with (
            patch.object(svc, "add_message", lambda _d, _c, role, content: stored.append((role, content))),
            patch.object(svc, "safe_receive_response", _fake_receive(["Hello ", "world", "!"])),
        ):
            connected = await router._forward_chunks(ws, session.send_message("hi"))
        return connected, ws.sent

    connected, sent = asyncio.run(run())

    assert connected is False
    assert sent == [{"type": "text", "content": "Hello "}]
    # Full answer still stored even though the client only saw the first chunk
    assert stored == [("user", "hi"), ("assistant", "Hello world!")]


def test_partial_response_persisted_when_stream_is_aborted():
    stored: list[tuple[str, str]] = []

    async def run():
        session = _ready_session()
        with (
            patch.object(svc, "add_message", lambda _d, _c, role, content: stored.append((role, content))),
            patch.object(svc, "safe_receive_response", _fake_receive(["partial", " rest"])),
        ):
            gen = session.send_message("hi")
            await gen.__anext__()
            await gen.aclose()

    asyncio.run(run())
    assert stored == [("user", "hi"), ("assistant", "partial")]


def test_create_session_reuses_live_session_for_same_conversation():
    async def run():
        with patch.dict(svc._sessions, clear=True):
            existing = _ready_session(conversation_id=7)
            svc._sessions["proj"] = existing

            same = await svc.create_session("proj", Path("/tmp/proj"), conversation_id=7)
            assert same is existing

            other = await svc.create_session("proj", Path("/tmp/proj"), conversation_id=8)
            assert other is not existing
            assert svc._sessions["proj"] is other

    asyncio.run(run())


def test_resume_waits_for_in_flight_response():
    stored: list[tuple[str, str]] = []
    order: list[str] = []

    async def run():
        session = _ready_session()
        gate = asyncio.Event()

        def add(_d, _c, role, content):
            stored.append((role, content))
            order.append(f"stored:{role}")

        async def consume_message():
            async for _ in session.send_message("hi"):
                pass

        async def consume_resume():
            async for chunk in session.resume():
                order.append(chunk["type"])

        with (
            patch.object(svc, "add_message", add),
            patch.object(svc, "safe_receive_response", _fake_receive(["a", "b"], gate)),
        ):
            msg_task = asyncio.create_task(consume_message())
            await asyncio.sleep(0)
            resume_task = asyncio.create_task(consume_resume())
            await asyncio.sleep(0.01)
            assert "response_done" not in order
            gate.set()
            await asyncio.gather(msg_task, resume_task)

    asyncio.run(run())
    assert stored[-1] == ("assistant", "ab")
    assert order.index("stored:assistant") < order.index("response_done")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
