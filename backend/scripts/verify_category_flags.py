"""Read-only: validate physical 9 category columns, 3 region fields and 342 teammate CSV rows.

From backend/: python -m scripts.verify_category_flags
"""
from collections import Counter
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Announcement, CATEGORY_FIELD_TO_ATTR
from scripts.import_mappings import load_map


def verify(region_path=Path('data/region_map.csv'), category_path=Path('data/category_map.csv')):
    regions=load_map(region_path,'region')
    categories=load_map(category_path,'category')
    issues=[]
    with SessionLocal() as session:
        rows=session.scalars(select(Announcement)).all()
        if len(rows)!=len(regions) or len(rows)!=len(categories):
            issues.append(f'DB 공고 {len(rows)}, 지역 CSV {len(regions)}, 카테고리 CSV {len(categories)}')
        for a in rows:
            aid=a.announcement_id
            if aid not in regions or aid not in categories:
                issues.append(f'{aid}: CSV mapping missing');continue
            expected_region=regions[aid]
            for col in ('region','seoul_gu','has_text'):
                if getattr(a,col)!=expected_region[col]:issues.append(f'{aid}: {col} mismatch')
            expected_cats=categories[aid]
            if a.support_types!=expected_cats:issues.append(f'{aid}: JSON support_types mismatch')
            if a.category_display!=', '.join(expected_cats):issues.append(f'{aid}: 카테고리 mismatch')
            for cat,attr in CATEGORY_FIELD_TO_ATTR.items():
                if getattr(a,attr)!=int(cat in expected_cats):issues.append(f'{aid}: {cat} 0/1 mismatch')
        counts=Counter()
        for a in rows:
            counts[a.region]+=1
            for cat,attr in CATEGORY_FIELD_TO_ATTR.items():
                if getattr(a,attr)==1:counts[cat]+=1
    print('공고:',len(rows),'건')
    print('지역:',{k:counts[k] for k in ('서울','전국','타지역')})
    print('카테고리:',{k:counts[k] for k in CATEGORY_FIELD_TO_ATTR})
    print('검증 오류:',len(issues),'건')
    if issues:
        print('\n'.join(issues[:10]));raise RuntimeError(f'CSV mapping mismatch: {len(issues)}')
    print('PASS: 모든 342건 CSV mapping과 DB 컬럼 일치')

if __name__=='__main__':verify()
