import pytest


@pytest.mark.asyncio
async def test_first_run_does_not_exit_before_initializer(tmp_path, monkeypatch):
    import autocoder.agent.agent as agent_mod

    class Sentinel(Exception):
        pass

    def _boom(*args, **kwargs):
        raise Sentinel("initializer session should start (create_client invoked)")

    monkeypatch.setattr(agent_mod, "create_client", _boom)

    with pytest.raises(Sentinel):
        await agent_mod.run_autonomous_agent(tmp_path, model="dummy", max_iterations=1)

