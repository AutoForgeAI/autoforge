from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencode_adapter import AssistantMessage, OpencodeClient, TextBlock, ToolResultBlock


@pytest.mark.asyncio
async def test_context_and_query_uses_session_and_provider():
    mock_client = MagicMock()
    mock_client.session.create = AsyncMock(return_value=SimpleNamespace(id="sess1"))
    mock_client.app.providers = AsyncMock(return_value=SimpleNamespace(providers=[SimpleNamespace(id="prov1")]))
    mock_client.session.chat = AsyncMock()
    mock_client.aclose = AsyncMock()

    with patch("opencode_adapter.AsyncOpencode", return_value=mock_client):
        client = OpencodeClient(Path("/tmp"), model="default", yolo_mode=False)
        await client.__aenter__()
        assert client._session.id == "sess1"
        assert client._provider_id == "prov1"

        await client.query("Hello world")
        mock_client.session.chat.assert_awaited()
        called_args = mock_client.session.chat.call_args[0]
        # First positional arg is session id
        assert called_args[0] == "sess1"

        # kwargs include model_id and parts
        kwargs = mock_client.session.chat.call_args.kwargs
        assert kwargs["model_id"] == "default"
        assert kwargs["parts"][0]["text"] == "Hello world"

        await client.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_receive_response_yields_text_and_tool_result():
    # Prepare messages sequences: one message with text part, then one with tool completed
    text_part = SimpleNamespace(type="text", text="Hello from Opencode")
    tool_state = SimpleNamespace(status="completed", output="Wrote file")
    tool_part = SimpleNamespace(type="tool", tool="Write", state=tool_state)

    msg1 = SimpleNamespace(info=SimpleNamespace(role="assistant"), parts=[text_part])
    msg2 = SimpleNamespace(info=SimpleNamespace(role="assistant"), parts=[tool_part])


    mock_client = MagicMock()
    mock_client.session.create = AsyncMock(return_value=SimpleNamespace(id="sess1"))
    mock_client.app.providers = AsyncMock(return_value=SimpleNamespace(providers=[SimpleNamespace(id="prov1")]))
    # Ensure aclose is awaitable
    mock_client.aclose = AsyncMock()

    # messages returns cumulative lists (adapter expects cumulative history)
    calls = [ [msg1], [msg1, msg2], [msg1, msg2], [], [], [] ]
    async def fake_messages(session_id):
        if calls:
            return calls.pop(0)
        return []

    mock_client.session.messages = AsyncMock(side_effect=fake_messages)

    with patch("opencode_adapter.AsyncOpencode", return_value=mock_client):
        client = OpencodeClient(Path("/tmp"), model="default", yolo_mode=False)
        await client.__aenter__()

        results = []
        async for msg in client.receive_response():
            results.append(msg)

        # Two messages expected
        assert len(results) == 2
        first = results[0]
        second = results[1]

        assert isinstance(first, AssistantMessage)
        assert isinstance(first.content[0], TextBlock)
        assert first.content[0].text == "Hello from Opencode"

        # Tool result should be ToolResultBlock with content 'Wrote file'
        assert any(isinstance(b, ToolResultBlock) for b in second.content)
        tool_block = next(b for b in second.content if isinstance(b, ToolResultBlock))
        assert tool_block.content == "Wrote file"

        await client.__aexit__(None, None, None)
