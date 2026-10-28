"""Tests for serving unchanged frontend build and keeping FastAPI endpoints."""
import app.fullstack as fullstack
from fastapi.testclient import TestClient

client = TestClient(fullstack.app)

def test_backend_health_and_matching():
    status = client.get('/health')
    assert status.status_code == 200
    assert status.json()['database'] == 'connected'
    resp = client.post('/api/support-match', json={'text': '29살 서울 마포구 카페 창업을 준비 중이고 자금이 부족합니다.'})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get('results'), list)
    assert body['meta']

def test_without_frontend_build_remains_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(fullstack, 'DIST', tmp_path / 'not-built')
    resp = client.get('/')
    assert resp.status_code == 503
    assert '빌드' in resp.json()['detail']

def test_original_frontend_build_and_react_routes(monkeypatch, tmp_path):
    dist = tmp_path / 'dist'
    assets = dist / 'assets'
    assets.mkdir(parents=True)
    (dist / 'index.html').write_text('<html><body>ORIGINAL FRONTEND</body></html>', encoding='utf8')
    (assets / 'test.js').write_text('console.log(1);', encoding='utf8')
    monkeypatch.setattr(fullstack, 'DIST', dist)
    for path in ('/', '/support-match', '/support-match/results', '/support-match/detail/123'):
        res = client.get(path)
        assert res.status_code == 200
        assert 'ORIGINAL FRONTEND' in res.text
    js=client.get('/assets/test.js')
    assert js.status_code == 200
    assert 'console.log' in js.text
    assert client.get('/assets/nonexistent.js').status_code == 404
    assert client.get('/api/unknown').status_code == 404
    assert client.get('/api/support-match').status_code == 405
    assert client.get('/health').json()['database'] == 'connected'
