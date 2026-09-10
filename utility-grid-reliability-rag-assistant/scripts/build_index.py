"""
Utility Grid Reliability RAG Assistant — index build
Extract: text from 6 public DOE/FERC/NERC grid-reliability PDFs
Transform: page-level text -> overlapping chunks
Load: dense embeddings (sentence-transformers) into a FAISS similarity index
"""
import os
import glob
import json
import pypdf
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

CHUNK_SIZE = 900       # characters
CHUNK_OVERLAP = 150    # characters
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

DOC_LABELS = {
    "DOE_A_More_Resilient_Grid.pdf": "DOE — A More Resilient Grid (2016)",
    "DOE_Economic_Benefits_Grid_Resilience.pdf": "DOE — Economic Benefits of Increasing Electric Grid Resilience to Weather Outages (2013)",
    "DOE_Grid_Modernization_Strategy_2024.pdf": "DOE — Grid Modernization Strategy (2024)",
    "FERC_Electric_Reliability_Primer.pdf": "FERC — Electric Reliability Primer",
    "FERC_Summer_Assessment_2025.pdf": "FERC — Summer Energy Market and Electric Reliability Assessment (2025)",
    "NERC_Reliability_Principles.pdf": "NERC — Reliability Principles",
}


def extract_pages(pdf_path):
    reader = pypdf.PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = " ".join(text.split())  # collapse whitespace/newlines
        if text.strip():
            pages.append((i + 1, text))
    return pages


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end]
        if len(chunk.strip()) > 50:  # skip near-empty tail fragments
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


def main():
    log_lines = ["=== Utility Grid Reliability RAG — index build ==="]
    records = []  # {doc, page, chunk_id, text}

    pdf_files = sorted(glob.glob(os.path.join(RAW_DIR, "*.pdf")))
    for pdf_path in pdf_files:
        fname = os.path.basename(pdf_path)
        label = DOC_LABELS.get(fname, fname)
        pages = extract_pages(pdf_path)
        doc_chunks = 0
        for page_num, page_text in pages:
            for chunk in chunk_text(page_text):
                records.append({
                    "doc": label,
                    "source_file": fname,
                    "page": page_num,
                    "chunk_id": len(records),
                    "text": chunk,
                })
                doc_chunks += 1
        msg = f"[{fname}] {len(pages)} pages with extractable text -> {doc_chunks} chunks"
        print(msg)
        log_lines.append(msg)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(PROCESSED_DIR, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nEmbedding {len(records)} chunks with {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [r["text"] for r in records]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True,
                               convert_to_numpy=True, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # cosine similarity via normalized inner product
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, os.path.join(PROCESSED_DIR, "faiss.index"))

    summary = (f"[Embed] {len(records)} chunks across {len(pdf_files)} documents -> "
               f"{dim}-dim vectors ({EMBEDDING_MODEL}), FAISS IndexFlatIP")
    print(summary)
    log_lines.append(summary)

    with open(os.path.join(OUTPUT_DIR, "index_build_log.txt"), "w") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    main()
