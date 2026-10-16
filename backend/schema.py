"""Generate an additive PostgreSQL script without connecting to any database."""
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from .models import Base, WORKFLOW_TABLES


def ensure_workflow_columns(engine):
    """Finish pre-release v4 tables if a development auto-reloader saw them early."""
    from sqlalchemy import inspect,text
    additions={'amiga_uploader_confirmations':{'item_count':'INTEGER NOT NULL DEFAULT 0'},
               'amiga_agent_turns':{'request_hash':'VARCHAR(64)'}}
    with engine.begin() as connection:
        if engine.dialect.name=='sqlite':connection.execute(text('BEGIN IMMEDIATE'))
        for table,columns in additions.items():
            present={c['name'] for c in inspect(connection).get_columns(table)}
            for name,definition in columns.items():
                if name not in present:
                    optional='IF NOT EXISTS ' if engine.dialect.name=='postgresql' else ''
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {optional}{name} {definition}'))


def postgres_migration():
    dialect = postgresql.dialect()
    statements = ['-- AMIGA workspace schema v1. Existing legacy tables are untouched.', 'BEGIN;']
    for table in Base.metadata.sorted_tables:
        if table.name in {'amiga_local_credentials', 'amiga_request_lifecycle'} | WORKFLOW_TABLES:
            continue  # v1 is retained for existing installations; v2 is additive.
        statements.append(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip() + ';')
        for index in sorted(table.indexes, key=lambda i: i.name):
            statements.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)) + ';')
    statements += ["INSERT INTO amiga_settings (key,value) VALUES ('schema_version','1'),('bootstrap_consumed','0') ON CONFLICT (key) DO NOTHING;", 'COMMIT;']
    return '\n\n'.join(statements) + '\n'


def local_auth_migration():
    table = Base.metadata.tables['amiga_local_credentials']
    return ('-- AMIGA v2: local bcrypt credentials. Existing users/documents are preserved.\nBEGIN;\n'
            + str(CreateTable(table, if_not_exists=True).compile(dialect=postgresql.dialect())).strip() + ';\n'
            + "UPDATE amiga_settings SET value='2' WHERE key='schema_version' AND value='1';\nCOMMIT;\n")


def request_lifecycle_migration():
    table = Base.metadata.tables['amiga_request_lifecycle']
    return ('-- AMIGA v3: administrative closure. Existing requests default to OPEN.\nBEGIN;\n'
            + str(CreateTable(table, if_not_exists=True).compile(dialect=postgresql.dialect())).strip() + ';\n'
            + "UPDATE amiga_settings SET value='3' WHERE key='schema_version' AND value='2';\nCOMMIT;\n")


def workflow_migration():
    statements=['-- AMIGA v4: versioned uploader confirmation, Luna agents and optional Telegram.','BEGIN;']
    dialect=postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        if table.name not in WORKFLOW_TABLES:
            continue
        statements.append(str(CreateTable(table,if_not_exists=True).compile(dialect=dialect)).strip()+';')
        for index in sorted(table.indexes,key=lambda i:i.name):
            statements.append(str(CreateIndex(index,if_not_exists=True).compile(dialect=dialect))+';')
    statements += ["UPDATE amiga_settings SET value='4' WHERE key='schema_version' AND value='3';",'COMMIT;']
    return '\n\n'.join(statements)+'\n'


if __name__ == '__main__':
    print(postgres_migration(), end='')
