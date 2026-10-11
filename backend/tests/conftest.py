import os
import atexit
import uuid
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Isolated file database permits independent worker and API connections.
_tmp = tempfile.TemporaryDirectory(prefix='sprintgraph-tests-')
test_url = os.environ.get('SPRINTGRAPH_TEST_DATABASE_URL')
if test_url:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema
    parsed = make_url(test_url)
    if parsed.get_backend_name() != 'postgresql' or not (parsed.database or '').endswith('_test'):
        raise RuntimeError('PostgreSQL tests require a dedicated database whose name ends with _test')
    schema = 'sgtest_' + uuid.uuid4().hex
    administrative_engine = create_engine(parsed)
    with administrative_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    os.environ['DATABASE_URL'] = parsed.update_query_dict(
        {'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)

    def cleanup_schema():
        engine.dispose()
        with administrative_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        administrative_engine.dispose()

    atexit.register(cleanup_schema)
else:
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db')
os.environ['JWT_SECRET'] = 'test-secret-is-only-for-isolated-tests-0001'
os.environ['DEMO_PASSWORD'] = 'test-demo-password-1234'
os.environ['GITHUB_WEBHOOK_SECRET'] = 'test-webhook-secret'
os.environ['JIRA_WEBHOOK_SECRET'] = 'test-jira-secret'
os.environ['MODE'] = 'demo'
os.environ['LLM_PROVIDER'] = 'demo'
from app.db import engine, Session  # noqa: E402
from app.models import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    yield

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def headers(client):
    response = client.post('/api/auth/login', json={'email': 'admin@sprintgraph.local', 'password': os.environ['DEMO_PASSWORD']})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}

@pytest.fixture
def db():
    with Session() as session:
        yield session
