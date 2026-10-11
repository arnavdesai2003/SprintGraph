"""Run real adapters against demo data and mocked HTTP provider failures offline."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from app.config import settings
from app.integrations.clients import Clients, ProviderError

async def check():
    client = Clients()
    pr = await client.pull_request('sprintgraph/demo', 43)
    assert pr['number'] == 43 and len(pr['files']) == 2 and len(pr['commits']) == 1
    sprint = await client.sprint(SimpleNamespace(jira_board_id=1, jira_key='SG'))
    assert len(sprint['issues']) == 4 and sprint['id'] == 'demo-sprint-12'
    try:
        await client.pull_request('../invalid', 1)
    except ProviderError:
        pass
    else:
        raise AssertionError('Invalid repository accepted')
    with patch.object(settings(), 'mode', 'live'), patch.object(settings(), 'github_token', ''):
        try:
            await client.pull_request('sprintgraph/demo', 1)
        except ProviderError:
            pass
        else:
            raise AssertionError('Missing GitHub credentials accepted')
    error = httpx.HTTPStatusError('sensitive-provider-body', request=httpx.Request('GET', 'https://api.github.com'), response=httpx.Response(429))
    with patch.object(httpx.AsyncClient, 'get', AsyncMock(side_effect=error)):
        try:
            await client.request('https://api.github.com')
        except ProviderError as exc:
            assert '429' in str(exc) and 'sensitive' not in str(exc)
        else:
            raise AssertionError('Provider failure ignored')
    print('PASS: demo PR/sprint adapters, repository validation, missing credentials and safe rate-limit failure')

asyncio.run(check())
