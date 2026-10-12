"""Offline Gemini-compatible HTTP contract and safety tests."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch
from app.agents.inference import configuration, describe
from app.config import Settings
from app.integrations.clients import ProviderError
import httpx


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.config = Settings(_env_file=None, jwt_secret='test-only-' * 8,
            llm_provider='openai-compatible', llm_inference_enabled=True,
            llm_base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
            llm_model='gemini-3.1-flash-lite', llm_api_key='private-test-key')
        self.analysis = {'summary': 'SPRIN-1 adds webhook validation.', 'risks': ['Check replay handling'],
                         'testing': ['Test invalid signatures'], 'recommendations': ['Review before merging']}

    def call(self, response=None, error=None):
        post = AsyncMock(side_effect=error, return_value=response)
        with patch('app.agents.inference.settings', return_value=self.config), patch('httpx.AsyncClient.post', post):
            result = asyncio.run(describe({'number': 2}, {}))
        return result, post

    def response(self, status=200, content=None, headers=None):
        return httpx.Response(status, headers=headers, json={'id': 'chatcmpl-gemini-fixture',
            'object': 'chat.completion', 'model': self.config.llm_model,
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant',
                'content': json.dumps(self.analysis) if content is None else content}}],
            'usage': {'prompt_tokens': 150, 'completion_tokens': 60, 'total_tokens': 210}})

    def test_gemini_contract_and_validated_response(self):
        result, post = self.call(self.response())
        self.assertEqual(result, self.analysis)
        self.assertEqual(post.await_count, 1)
        self.assertEqual(post.await_args.args[0], self.config.llm_base_url + 'chat/completions')
        payload = post.await_args.kwargs['json']
        self.assertEqual(payload['model'], 'gemini-3.1-flash-lite')
        self.assertEqual(payload['response_format'], {'type': 'json_object'})
        self.assertNotIn('temperature', payload)
        self.assertNotIn('tools', payload)

    def test_disabled_never_calls_provider(self):
        self.config.llm_inference_enabled = False
        with patch('httpx.AsyncClient.post', AsyncMock()) as post, patch('app.agents.inference.settings', return_value=self.config):
            with self.assertRaises(ProviderError):
                asyncio.run(describe({}, {}))
            post.assert_not_awaited()

    def test_validation_makes_no_network_requests(self):
        with patch('httpx.AsyncClient.post', side_effect=AssertionError('network')):
            result = configuration(self.config)
        self.assertEqual(result['network_requests'], 0)
        self.assertNotIn('private-test-key', json.dumps(result))
        self.assertFalse(result['fallback_enabled'])

    def test_auth_and_bad_request_terminal(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.call(self.response(status))
            self.assertFalse(caught.exception.retryable)
            self.assertNotIn('private-test-key', str(caught.exception))

    def test_rate_limit_and_provider_failure_retry(self):
        for status in (429, 503):
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.call(self.response(status, headers={'retry-after': '17'}))
            self.assertTrue(caught.exception.retryable)
            self.assertEqual(caught.exception.retry_after, 17)

    def test_timeout_safe_and_retryable(self):
        with self.assertRaises(ProviderError) as caught:
            self.call(error=httpx.ReadTimeout('private-test-key'))
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn('private-test-key', str(caught.exception))

    def test_malformed_and_extra_execution_fields_rejected(self):
        for content in ('not json', 'null', json.dumps({**self.analysis, 'command': 'execute'})):
            with self.subTest(content=content), self.assertRaises(ProviderError) as caught:
                self.call(self.response(content=content))
            self.assertFalse(caught.exception.retryable)

    def test_invalid_configuration_never_falls_back(self):
        for url in ('http://example.invalid/v1', 'https://secret@example.invalid/v1',
                    'https://generativelanguage.googleapis.com/wrong'):
            self.config.llm_base_url = url
            with self.assertRaises(ProviderError):
                configuration(self.config)
