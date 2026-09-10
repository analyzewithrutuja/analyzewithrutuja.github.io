"""
Utility Grid Reliability RAG Assistant — retrieval-only query utility
Loads the FAISS index built by build_index.py and returns the top-k most
relevant chunks (with document + page provenance) for a natural-language
question. Used standalone for retrieval-quality validation, and imported
by rag_app.py for the full retrieve-then-generate pipeline.
"""
import os
import json
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_model = None
_index = None
_records = None


def _load():
    global _model, _index, _records
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
        _index = faiss.read_index(os.path.join(PROCESSED_DIR, "faiss.index"))
        _records = [json.loads(l) for l in open(
            os.path.join(PROCESSED_DIR, "chunks.jsonl"), encoding="utf-8")]
    return _model, _index, _records


def retrieve(query, k=4):
    model, index, records = _load()
    q_emb = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
    scores, idx = index.search(q_emb.astype(np.float32), k)
    results = []
    for score, i in zip(scores[0], idx[0]):
        if i == -1:
            continue
        r = records[i]
        results.append({"score": float(score), "doc": r["doc"], "page": r["page"],
                         "text": r["text"]})
    return results


if __name__ == "__main__":
    test_queries = [
        "What is grid resilience and how is it different from reliability?",
        "How does the grid respond to extreme weather events?",
        "What are the benefits of grid modernization investments?",
        "How is electric reliability measured or assessed in the summer?",
        "What are NERC's core reliability principles?",
    ]
    for q in test_queries:
        print(f"\n=== Q: {q} ===")
        for r in retrieve(q, k=3):
            print(f"  [{r['score']:.3f}] {r['doc']} (p.{r['page']}): {r['text'][:180]}...")
