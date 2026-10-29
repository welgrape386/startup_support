"""
V2b 원문 문단 임베딩 만들기 (오래 걸려서 따로 실행)

바뀐 문단만 계산하는 방식
- 문단마다 지문(md5 해시)을 붙여 cache/emb_store/에 벡터를 저장해둠
- 원문이 업데이트돼도(v8 → v9 OCR 등) 글자가 같은 문단은 저장된 벡터를 그대로 쓰고, 바뀐 문단만 새로 계산
- 256개 계산할 때마다 저장 → 중간에 끊겨도 다시 실행하면 이어서 계산
- 다 끝나면 지금 문단 순서대로 모아 cache/{OUT_NAME} 저장 (retrievers.V1이 이 파일을 불러씀)

사용법
  python build_emb.py                       바뀐 문단만 계산 (진행 상황: cache/build_emb.log)
  python build_emb.py --import 파일.npy     코랩 등에서 계산한 결과를 저장소에 등록 (지금 문단 순서와 같아야 함)
설정(모델·최대 길이·정규화)을 바꾸면 벡터가 달라지므로 STORE 폴더 이름도 바꿔야 함
"""
import sys, json, time, hashlib
import numpy as np
from retrievers import original_passages, bge_m3, CACHE

OUT_NAME = "emb_v2b_v8_passage500.npy"              # eval_search.py에서 불러오는 이름
STORE = CACHE / "emb_store_bge-m3_len512"           # 지문 → 벡터 저장소 (모델·설정별로 하나)
LOG = CACHE / "build_emb.log"
STEP = 256

def log(msg):
    print(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

def key(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def load_store():
    STORE.mkdir(parents=True, exist_ok=True)
    kf, vf = STORE / "keys.json", STORE / "vecs.npy"
    if kf.exists():
        keys = json.load(open(kf, encoding="utf-8"))
        return keys, np.load(vf)
    return [], np.zeros((0, 1024), dtype=np.float32)

def save_store(keys, vecs):
    np.save(STORE / "vecs.npy", vecs)                 # 벡터 먼저, 키 나중 (중간에 끊겨도 키 > 벡터가 되지 않게)
    json.dump(keys, open(STORE / "keys.json", "w", encoding="utf-8"))

texts, _ = original_passages()
keys, vecs = load_store()
index = {k: i for i, k in enumerate(keys)}

if len(sys.argv) == 3 and sys.argv[1] == "--import":
    E = np.load(sys.argv[2]).astype(np.float32)
    assert len(E) == len(texts), f"조각 수가 다름: 파일 {len(E)} / 지금 문단 {len(texts)} → 같은 원문 버전으로 만든 파일인지 확인"
    new = [(key(t), e) for t, e in zip(texts, E) if key(t) not in index]
    if new:
        keys += [k for k, _ in new]; vecs = np.vstack([vecs, np.stack([e for _, e in new])])
        save_store(keys, vecs)
    log(f"등록: {sys.argv[2]} → 새 문단 {len(new)}개 저장소에 추가 (저장소 총 {len(keys)}개)")
else:
    todo = list(dict.fromkeys(key(t) for t in texts if key(t) not in index))   # 중복 문단은 한 번만
    text_of = {key(t): t for t in texts}
    log(f"시작: 문단 {len(texts)}개 중 새로 계산할 것 {len(todo)}개 (저장소 {len(keys)}개 재사용)")
    if todo:
        model = bge_m3()
        model.max_seq_length = 512                    # 문단이 약 500자라 512토큰이면 충분. 기본값(8192)보다 훨씬 빠름
        t0 = time.time()
        for s in range(0, len(todo), STEP):
            batch = todo[s:s + STEP]
            E = model.encode([text_of[k] for k in batch], normalize_embeddings=True, batch_size=16)
            keys += batch; vecs = np.vstack([vecs, E.astype(np.float32)])
            save_store(keys, vecs)
            log(f"{min(s + STEP, len(todo))}/{len(todo)} 계산 ({(time.time() - t0) / 60:.1f}분 경과)")

# 지금 문단 순서대로 모아서 저장
index = {k: i for i, k in enumerate(keys)}          # 등록·계산으로 늘어난 저장소 기준으로 다시 만듦
missing = [t for t in texts if key(t) not in index]
if missing:
    log(f"아직 계산 안 된 문단 {len(missing)}개 → python build_emb.py 실행 필요")
else:
    E = vecs[[index[key(t)] for t in texts]]
    np.save(CACHE / OUT_NAME, E)
    log(f"완료: {OUT_NAME} {E.shape}")
