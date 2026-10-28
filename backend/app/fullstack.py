"""Serve the ORIGINAL, UNMODIFIED Vite build at the same origin as FastAPI.

From backend/ run: python -m uvicorn app.fullstack:app --reload --port 8000
From frontend/ run npm ci && npm run build once before starting.

Frontend fetch('/api/support-match') will reach FastAPI on the same host.
"""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from app.main import app

# Support both layouts without changing any frontend code:
# (a) local bundle: project/frontend/dist + project/backend
# (b) original GitHub repo: repo/dist + repo/backend
REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPO_ROOT / 'frontend' if (REPO_ROOT / 'frontend').is_dir() else REPO_ROOT
DIST = FRONTEND_ROOT / 'dist'

@app.get('/', include_in_schema=False)
def frontend_home():
    index = DIST / 'index.html'
    if not index.is_file():
        return JSONResponse(
            status_code=503,
            content={'detail': '프론트 빌드가 없습니다. frontend 폴더에서 npm ci, npm run build를 실행하세요.'},
        )
    return FileResponse(index)

@app.get('/{frontend_path:path}', include_in_schema=False)
def frontend_pages(frontend_path: str):
    # All real API routes have already been registered in app.main.
    # Never serve the HTML frontend as a response to an unknown API URL.
    if frontend_path == 'api/support-match':
        raise HTTPException(status_code=405, detail='Method Not Allowed: POST required')
    if frontend_path.startswith(('api/', 'docs/', 'redoc/', 'health/')) or frontend_path in {'api', 'docs', 'redoc', 'health', 'openapi.json'}:
        raise HTTPException(status_code=404, detail='Not Found')

    resolved_dist = DIST.resolve()
    target = (DIST / frontend_path).resolve()
    if target != resolved_dist and resolved_dist not in target.parents:
        raise HTTPException(status_code=404, detail='Not Found')
    if target.is_file():
        return FileResponse(target)
    # React Router: unknown browser routes return index.html, not HTTP 404.
    # But never return HTML for a missing JS/CSS/static asset.
    if Path(frontend_path).suffix:
        raise HTTPException(status_code=404, detail='Static file not found')
    index = DIST / 'index.html'
    if not index.is_file():
        return JSONResponse(status_code=503, content={'detail': '프론트 빌드가 없습니다. frontend 에서 npm run build 실행'})
    return FileResponse(index)
