import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from app.integrations.check import check
from app.integrations.clients import ProviderError


class IntegrationCheckTests(unittest.TestCase):
    def setUp(self):
        self.project = SimpleNamespace(github_repository='test/repo')
        self.db = MagicMock()
        self.db.get.return_value = self.project
        self.client = SimpleNamespace(
            pull_request=AsyncMock(return_value={'number': 1, 'files': [], 'commits': []}),
            sprint=AsyncMock(return_value={'id': '12', 'issues': []}))

    def invoke(self, provider='all', number=1):
        with patch('app.integrations.check.Session') as session, patch(
                'app.integrations.check.Clients', return_value=self.client), patch(
                'app.integrations.check.settings', return_value=SimpleNamespace(mode='live')):
            session.return_value.__enter__.return_value = self.db
            return asyncio.run(check(2, number, provider))

    def test_jira_can_be_checked_without_github_or_pr_number(self):
        result = self.invoke('jira', None)
        self.client.pull_request.assert_not_awaited()
        self.client.sprint.assert_awaited_once_with(self.project)
        self.assertEqual(result['mode'], 'live')
        self.assertEqual(result['llm_calls'], 0)
        self.assertNotIn('pull_request', result)

    def test_github_can_be_checked_without_jira(self):
        result = self.invoke('github')
        self.client.sprint.assert_not_awaited()
        self.assertEqual(result['pull_request']['number'], 1)

    def test_failure_identifies_github_and_retains_retry_metadata(self):
        self.client.pull_request.side_effect = ProviderError('Provider request failed (404)', retryable=False)
        with self.assertRaisesRegex(ProviderError, 'GitHub PR retrieval') as caught:
            self.invoke()
        self.assertFalse(caught.exception.retryable)
        self.client.sprint.assert_not_awaited()

    def test_failure_identifies_jira_and_retains_provider_delay(self):
        self.client.sprint.side_effect = ProviderError('Provider request failed (429)', retry_after=60)
        with self.assertRaisesRegex(ProviderError, 'Jira sprint retrieval') as caught:
            self.invoke()
        self.assertEqual(caught.exception.retry_after, 60)

    def test_missing_project_prevents_provider_calls(self):
        self.db.get.return_value = None
        with self.assertRaisesRegex(ProviderError, 'Project does not exist'):
            self.invoke()
        self.client.pull_request.assert_not_awaited()
        self.client.sprint.assert_not_awaited()

    def test_invalid_selection_or_missing_number_prevents_provider_calls(self):
        for provider, number in [('shell', 1), ('github', None), ('github', True)]:
            with self.subTest(provider=provider, number=number), self.assertRaises(ProviderError):
                self.invoke(provider, number)
        self.client.pull_request.assert_not_awaited()
        self.client.sprint.assert_not_awaited()
