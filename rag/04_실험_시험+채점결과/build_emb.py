"""
원문 문단 임베딩 만들기 (오래 걸려서 따로 실행)

    python build_emb.py                    바뀐 문단만 계산
    python build_emb.py --import 파일.npy  코랩에서 만든 결과 등록

- 문단마다 md5 키로 벡터를 저장해 두고, 원문이 바뀌어도 같은 문단은 다시 계산하지 않음
- 256개마다 저장해서 중간에 끊겨도 이어서 계산
- 끝나면 cache/emb_v2b_v8_passage500.npy 저장 (retrievers.V1이 씀)
- 모델이나 설정을 바꾸면 STORE 폴더 이름도 바꿀 것
"""
import sys, json, time, hashlib
import numpy as np
from retrievers import original_passages, bge_m3, CACHE

OUT_NAME = "emb_v2b_v8_passage500.npy"
STORE = CACHE / "emb_store_bge-m3_len512"
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
        return json.load(open(kf, encoding="utf-8")), np.load(vf)
    return [], np.zeros((0, 1024), dtype=np.float32)

def save_store(keys, vecs):
    np.save(STORE / "vecs.npy", vecs)           # 벡터를 먼저 저장해야 키 수가 벡터 수보다 많아지지 않음
    json.dump(keys, open(STORE / "keys.json", "w", encoding="utf-8"))

texts, _ = original_passages()
keys, vecs = load_store()
index = {k: i for i, k in enumerate(keys)}

if len(sys.argv) == 3 and sys.argv[1] == "--import":
    E = np.load(sys.argv[2]).astype(np.float32)
    assert len(E) == len(texts), f"문단 수가 다름: 파일 {len(E)} / 지금 {len(texts)}"
    new = [(key(t), e) for t, e in zip(texts, E) if key(t) not in index]
    if new:
        keys += [k for k, _ in new]; vecs = np.vstack([vecs, np.stack([e for _, e in new])])
        save_store(keys, vecs)
    log(f"등록: {sys.argv[2]}, 새 문단 {len(new)}개 (저장소 {len(keys)}개)")
else:
    todo = list(dict.fromkeys(key(t) for t in texts if key(t) not in index))
    text_of = {key(t): t for t in texts}
    log(f"시작: 문단 {len(texts)}개 중 새로 계산 {len(todo)}개")
    if todo:
        model = bge_m3()
        model.max_seq_length = 512              # 문단이 500자 정도라 512면 충분하고 훨씬 빠름
        t0 = time.time()
        for s in range(0, len(todo), STEP):
            batch = todo[s:s + STEP]
            E = model.encode([text_of[k] for k in batch], normalize_embeddings=True, batch_size=16)
            keys += batch; vecs = np.vstack([vecs, E.astype(np.float32)])
            save_store(keys, vecs)
            log(f"{min(s + STEP, len(todo))}/{len(todo)} ({(time.time() - t0) / 60:.1f}분)")

index = {k: i for i, k in enumerate(keys)}
missing = [t for t in texts if key(t) not in index]
if missing:
    log(f"계산 안 된 문단 {len(missing)}개 남음. python build_emb.py 다시 실행")
else:
    E = vecs[[index[key(t)] for t in texts]]
    np.save(CACHE / OUT_NAME, E)
    log(f"완료: {OUT_NAME} {E.shape}")
