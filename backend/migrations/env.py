from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db import Base
from app import models, extended_models  # noqa: F401 register all tables
config=context.config
if config.config_file_name is not None: fileConfig(config.config_file_name)
db_url=os.getenv('DATABASE_URL','sqlite:///./data/startup_support.db')
if db_url.startswith('postgresql://'):
    db_url=db_url.replace('postgresql://','postgresql+psycopg://',1)
elif db_url.startswith('postgres://'):
    db_url=db_url.replace('postgres://','postgresql+psycopg://',1)
config.set_main_option('sqlalchemy.url',db_url)
target_metadata=Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'),target_metadata=target_metadata,literal_binds=True,dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():context.run_migrations()

def run_migrations_online():
    engine=engine_from_config(config.get_section(config.config_ini_section,{}),prefix='sqlalchemy.',poolclass=pool.NullPool)
    with engine.connect() as connection:
        if connection.dialect.name=='sqlite': connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        context.configure(connection=connection,target_metadata=target_metadata)
        with context.begin_transaction():context.run_migrations()
        connection.commit()  # sqlite Alembic version stamp must persist

if context.is_offline_mode():run_migrations_offline()
else:run_migrations_online()
