from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from app.db import engine
from app.models import Base
from app.seed import seed


def test_frozen_initial_migration_roundtrip_matches_models():
    # The test fixture creates an isolated database/schema, never the demo database.
    Base.metadata.drop_all(engine)
    configuration = Config('alembic.ini')
    command.upgrade(configuration, 'head')
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - {'alembic_version'} == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        columns = {column['name']: column for column in inspector.get_columns(name)}
        assert set(columns) == set(table.columns.keys())
        assert all(columns[column.name]['nullable'] == column.nullable for column in table.columns)
    seed()
    command.downgrade(configuration, 'base')
    assert set(inspect(engine).get_table_names()) <= {'alembic_version'}
    command.upgrade(configuration, 'head')
    seed()
