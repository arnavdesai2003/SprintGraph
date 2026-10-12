import asyncio
import unittest
from app.agents.tracing import node_trace, tracked


class TraceTests(unittest.TestCase):
    def test_sync_and_async_nodes_record_actual_completion(self):
        records = []
        token = node_trace.set(records)
        try:
            self.assertEqual(tracked('classify', lambda state: state)({'kind': 'PR'}), {'kind': 'PR'})
            async def node(state):
                return state
            self.assertEqual(asyncio.run(tracked('collect', node)({'data': 1})), {'data': 1})
        finally:
            node_trace.reset(token)
        self.assertEqual([r['node'] for r in records], ['classify', 'collect'])
        self.assertTrue(all(r['status'] == 'succeeded' and r['duration_ms'] >= 0 for r in records))
        self.assertTrue(all(set(r) == {'node', 'status', 'duration_ms'} for r in records))

    def test_failure_records_no_exception_message(self):
        records = []
        token = node_trace.set(records)
        try:
            def failing(state):
                raise ValueError('private provider message')
            with self.assertRaises(ValueError):
                tracked('collect', failing)({})
        finally:
            node_trace.reset(token)
        self.assertEqual(records[0]['status'], 'failed')
        self.assertNotIn('private', str(records))

    def test_async_timeout_retains_failed_node_observation(self):
        records = []
        token = node_trace.set(records)
        async def pending(state):
            await asyncio.sleep(1)
        async def execute():
            await asyncio.wait_for(tracked('collect', pending)({}), timeout=.01)
        try:
            with self.assertRaises(TimeoutError):
                asyncio.run(execute())
        finally:
            node_trace.reset(token)
        self.assertEqual(records[0]['status'], 'failed')
        self.assertIsNone(node_trace.get())
