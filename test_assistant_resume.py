"""
Tests for assistant chat persistence across panel close/reopen (issue #133).

Closing the assistant panel closes the WebSocket. The in-flight response must
still complete and be saved to history, and reopening the same conversation
must reuse the live session instead of killing it.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

from server.routers.assistant_chat import _forward_chunks
from server.services import assistant_chat_session as acs
from server.services.assistant_database import create_conversation, get_messages


# Class names matter: _query_claude dispatches on type(msg).__name__
class TextBlock:
    def __init__(self, text: str):
        self.text = text


class AssistantMessage:
    def __init__(self, *texts: str):
        self.content = [TextBlock(t) for t in texts]


class FakeClient:
    """Stands in for ClaudeSDKClient, streaming canned chunks."""

    def __init__(self, chunks: list[str], fail_after: int | None = None, delay: float = 0.0):
        self.chunks = chunks
        self.fail_after = fail_after
        self.delay = delay
        self.queries: list[str] = []

    async def query(self, message: str) -> None:
        self.queries.append(message)

    async def receive_response(self):
        for i, chunk in enumerate(self.chunks):
            if self.fail_after is not None and i == self.fail_after:
                raise RuntimeError("stream broke")
            await asyncio.sleep(self.delay)
            yield AssistantMessage(chunk)


class DisconnectingWebSocket:
    """WebSocket whose send_json fails after `ok_sends` successful sends."""

    def __init__(self, ok_sends: int):
        self.ok_sends = ok_sends
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        if len(self.sent) >= self.ok_sends:
            raise RuntimeError("Cannot call send once a close message has been sent")
        self.sent.append(data)


class AssistantResumeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        (self.project_dir / ".autoforge").mkdir()
        self.conv_id = int(create_conversation(self.project_dir, "proj").id)

    def tearDown(self):
        asyncio.run(acs.cleanup_all_sessions())
        self._tmp.cleanup()

    def _session(self, client: FakeClient) -> acs.AssistantChatSession:
        session = acs.AssistantChatSession("proj", self.project_dir, self.conv_id)
        session.client = client  # type: ignore[assignment]
        session._client_entered = True
        session._history_loaded = True
        return session

    def _contents(self) -> list[tuple[str, str]]:
        return [(m["role"], m["content"]) for m in get_messages(self.project_dir, self.conv_id)]

    def test_response_saved_when_client_disconnects_mid_stream(self):
        session = self._session(FakeClient(["Hello ", "there ", "friend"]))
        ws = DisconnectingWebSocket(ok_sends=1)

        connected = asyncio.run(_forward_chunks(ws, session.send_message("hi")))

        self.assertFalse(connected)
        self.assertEqual(len(ws.sent), 1)
        self.assertEqual(self._contents(), [("user", "hi"), ("assistant", "Hello there friend")])

    def test_partial_response_saved_when_stream_fails(self):
        session = self._session(FakeClient(["partial ", "never"], fail_after=1))

        async def run():
            return [chunk async for chunk in session.send_message("hi")]

        chunks = asyncio.run(run())

        self.assertEqual(chunks[-1]["type"], "error")
        self.assertEqual(self._contents(), [("user", "hi"), ("assistant", "partial ")])

    def test_resume_same_conversation_reuses_live_session(self):
        async def run():
            session = self._session(FakeClient([]))
            acs._sessions["proj"] = session
            same, reused = await acs.get_or_create_session("proj", self.project_dir, self.conv_id)
            other_id = int(create_conversation(self.project_dir, "proj").id)
            other, other_reused = await acs.get_or_create_session("proj", self.project_dir, other_id)
            return session, same, reused, other, other_reused

        session, same, reused, other, other_reused = asyncio.run(run())

        self.assertTrue(reused)
        self.assertIs(same, session)
        self.assertFalse(other_reused)
        self.assertIsNot(other, session)

    def test_wait_until_idle_waits_for_in_flight_response(self):
        session = self._session(FakeClient(["a", "b", "c"], delay=0.02))

        async def run():
            async def drain():
                async for _ in session.send_message("hi"):
                    pass

            task = asyncio.create_task(drain())
            await asyncio.sleep(0.01)
            busy = session.is_responding
            await session.wait_until_idle()
            history_after_wait = self._contents()
            await task
            return busy, history_after_wait

        busy, history = asyncio.run(run())

        self.assertTrue(busy)
        self.assertFalse(session.is_responding)
        self.assertEqual(history, [("user", "hi"), ("assistant", "abc")])


if __name__ == "__main__":
    unittest.main()
