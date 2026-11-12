"""One-time / idempotent DB bootstrap for a deployment environment; no user data writes."""
from __future__ import annotations
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Announcement
from scripts.ingest import main as ingest_main
from scripts.import_mappings import import_mappings

BASE=Path(__file__).resolve().parents[1]
def main():
    import os, sys
    os.chdir(BASE)
    command.upgrade(Config(str(BASE/'alembic.ini')), 'head')
    with SessionLocal() as session:
        total=session.scalar(select(func.count()).select_from(Announcement)) or 0
    if total==0:
        old=sys.argv
        try:
            sys.argv=['ingest']
            ingest_main()
        finally:
            sys.argv=old
    # No rewrite if DB already populated; normal idempotent sync maps only.
    import_mappings(BASE/'data/region_map.csv', BASE/'data/category_map.csv')
    print('DB bootstrap complete')
if __name__=='__main__':main()
