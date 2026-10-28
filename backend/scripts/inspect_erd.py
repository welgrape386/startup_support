"""Read actual DB schema (SQLite or PostgreSQL) and generate Mermaid ERD source."""
from pathlib import Path
from sqlalchemy import inspect, text
from app.db import engine

def main():
    insp=inspect(engine)
    tables=sorted(t for t in insp.get_table_names() if t!='alembic_version')
    lines=['erDiagram']
    fk_edges=[]
    for t in tables:
        lines.append('    '+t+' {')
        pk=set(insp.get_pk_constraint(t).get('constrained_columns') or [])
        fk_cols={c for f in insp.get_foreign_keys(t) for c in f['constrained_columns']}
        for col in insp.get_columns(t):
            typ=str(col['type']).replace(' ','_').replace('(', '_').replace(')', '')
            name=col['name'].replace(' ','_').replace('·','_')
            marker=' PK' if col['name'] in pk else ' FK' if col['name'] in fk_cols else ''
            lines.append('        '+typ+' '+name+marker)
        lines.append('    }')
        for fk in insp.get_foreign_keys(t):
            if fk['referred_table'] in tables:
                fk_edges.append('    '+fk['referred_table']+' ||--o{ '+t+' : "'+','.join(fk['constrained_columns'])+'"')
    lines[1:1]=fk_edges
    for t in tables:
        with engine.connect() as c:
            n=c.execute(text('SELECT COUNT(*) FROM "'+t+'"')).scalar_one()
        print(f'{t}: {n}건; columns: {len(insp.get_columns(t))}; FK: {len(insp.get_foreign_keys(t))}')
    file=Path(__file__).resolve().parents[1]/'docs/ERD_ACTUAL.mmd'
    file.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('ERD saved:',file)
if __name__=='__main__':main()
