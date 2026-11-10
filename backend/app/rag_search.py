"""RAG 검색 어댑터.

RAG 팀의 search_service.search()를 백엔드에서 부르는 얇은 층이다.
- 위치: 기본은 저장소 rag/04_실험_시험+채점결과 (RAG_DIR 환경변수로 바꿀 수 있음)
- 판정으로 넘기는 개수: 환경변수 SEARCH_TOP_K (기본 20)
- 실패하면 None을 돌려주고, 호출하는 쪽은 키워드 검색으로 대신한다.
- 이 모듈은 자격을 판정하지 않는다. 검색 순서만 준다.
"""
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parents[2] / 'rag' / '04_실험_시험+채점결과'
RAG_DIR = Path(os.environ.get('RAG_DIR', DEFAULT_DIR))
TOP_K = int(os.environ.get('SEARCH_TOP_K', '20'))      # 필터 이후 판정으로 넘길 개수
POOL = int(os.environ.get('RAG_POOL', '100'))          # 필터 전에 RAG에서 받아 둘 개수 (마감·지역 필터로 많이 빠지므로 넉넉히)

_loaded = None  # None: 아직 안 불러봄 / True: 사용 가능 / False: 사용 불가


def _load():
    global _loaded
    if _loaded is not None:
        return _loaded
    try:
        if str(RAG_DIR) not in sys.path:
            sys.path.insert(0, str(RAG_DIR))
        import search_service  # noqa: F401
        _loaded = True
    except Exception as e:  # 패키지 없음, 폴더 없음 등
        log.warning('RAG 검색을 쓸 수 없어 키워드 검색으로 대체합니다: %s', e)
        _loaded = False
    return _loaded


def search_ranked(query, user_gu='', stage='', need='', industry='', age=''):
    """[{pblancId, rank, score, evidence, evidence_from}, ...] 또는 실패 시 None."""
    if not query or not _load():
        return None
    try:
        from search_service import search
        return search(query, user_gu=user_gu or '', k=max(POOL, TOP_K), stage=stage or '', need=need or '', industry=industry or '', age=age or '')
    except Exception as e:
        log.warning('RAG 검색 중 오류, 키워드 검색으로 대체합니다: %s', e)
        return None


def warmup():
    """서버 시작 때 한 번 불러서 모델을 미리 올린다 (첫 요청이 오래 걸리지 않도록)."""
    search_ranked('준비')
