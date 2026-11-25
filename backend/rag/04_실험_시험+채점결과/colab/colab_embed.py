# ── 코랩에 이 셀 하나만 붙여넣고 실행 ──────────────────────────────
# 준비: 런타임 > 런타임 유형 변경 > T4 GPU 선택 후 실행
# 실행하면 파일 선택 버튼이 뜸 → passages_v8.json 올리기
# 끝나면 emb_v2b_v8_passage500.npy 가 자동으로 다운로드됨
#   → 노트북의 RAG/04_실험_시험+채점결과/cache/ 폴더에 넣기

!pip install -q sentence-transformers

import json, time, hashlib, torch, numpy as np
from google.colab import files
from sentence_transformers import SentenceTransformer

print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "없음 → 런타임 유형을 GPU로 바꾸세요")

up = files.upload()                                   # passages_v8.json 선택
data = json.load(open("passages_v8.json", encoding="utf-8"))
texts = data["texts"]
print("조각 수:", len(texts), "/ 확인용 코드:", hashlib.md5("\n".join(texts).encode()).hexdigest()[:8], "(114de25d 이어야 함)")

model = SentenceTransformer("BAAI/bge-m3", device="cuda")
model.max_seq_length = 512                            # 로컬 build_emb.py와 같은 설정
t0 = time.time()
E = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
print(f"완료: {E.shape}, {time.time() - t0:.0f}초")

np.save("emb_v2b_v8_passage500.npy", E.astype(np.float32))
files.download("emb_v2b_v8_passage500.npy")
