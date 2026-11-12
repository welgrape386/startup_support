"""Backup local SQLite and migrate v1 -> v2; run from backend directory."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from shutil import copy2
from alembic import command
from alembic.config import Config


def main():
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./data/startup_support.db')
    if not db_url.startswith('sqlite:///'):
        raise SystemExit('This helper is for local SQLite only; use Alembic with the deployment DB URL.')
    db_path = Path(db_url.removeprefix('sqlite:///'))
    if not db_path.is_file():
        raise SystemExit(f'DB file missing: {db_path}. For new DB use: alembic upgrade head')
    with sqlite3.connect(db_path) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'announcements', 'files', 'texts', 'conditions'}.issubset(tables):
            raise SystemExit('Unexpected DB schema: aborting safely')
        before = {name: c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in ['announcements','files','texts','conditions']}
        revisions = [r[0] for r in c.execute('SELECT version_num FROM alembic_version')] if 'alembic_version' in tables else []
    back = db_path.with_name(db_path.stem + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + db_path.suffix)
    copy2(db_path, back)
    print(f'Backup created: {back}')
    cfg = Config(str(Path('alembic.ini')))
    if not revisions:
        # Old v1 local DB shipped with 4 created tables, but no stamped migration revision.
        command.stamp(cfg, '20df4fd96723')
    elif revisions != ['20df4fd96723'] and revisions != ['7a3c20261024']:
        raise SystemExit('Unexpected Alembic revision. Restore backup; do not guess an upgrade.')
    command.upgrade(cfg, 'head')
    with sqlite3.connect(db_path) as c:
        c.execute('PRAGMA foreign_keys=ON')
        after = {name: c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in before}
        fk_errors = c.execute('PRAGMA foreign_key_check').fetchall()
        ntables = len({r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")})
    assert before == after, f'Existing row count changed! before={before} after={after}'
    assert not fk_errors, f'FK errors after upgrade: {fk_errors[:5]}'
    print('Migration successful:',before,'tables:',ntables,'FK errors:',len(fk_errors))

if __name__ == '__main__':main()
