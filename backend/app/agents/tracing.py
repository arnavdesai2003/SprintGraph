"""Per-attempt node observations; never capture provider payloads or credentials."""
from contextvars import ContextVar
from functools import wraps
from inspect import iscoroutinefunction
from time import perf_counter

node_trace: ContextVar[list | None] = ContextVar('workflow_node_trace', default=None)


def tracked(name, node):
    def begin():
        record = {'node': name, 'status': 'running'}
        trace = node_trace.get()
        if trace is not None:
            trace.append(record)
        return record, perf_counter()

    def finish(record, start, status):
        record.update(status=status, duration_ms=(perf_counter() - start) * 1000)

    if iscoroutinefunction(node):
        @wraps(node)
        async def asynchronous(*args, **kwargs):
            record, start = begin()
            try:
                output = await node(*args, **kwargs)
            except BaseException:
                finish(record, start, 'failed')
                raise
            finish(record, start, 'succeeded')
            return output
        return asynchronous

    @wraps(node)
    def synchronous(*args, **kwargs):
        record, start = begin()
        try:
            output = node(*args, **kwargs)
        except BaseException:
            finish(record, start, 'failed')
            raise
        finish(record, start, 'succeeded')
        return output
    return synchronous
