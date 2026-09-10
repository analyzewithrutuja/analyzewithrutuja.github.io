# Utility Grid Reliability RAG Assistant

A retrieval-augmented generation (RAG) application that answers questions
about electric grid reliability, resilience, and modernization using only
public DOE, FERC, and NERC source documents — grounding every answer in a
citation rather than the LLM's own (possibly outdated or hallucinated)
knowledge. Built as the GenAI/utilities-domain counterpart to my Diabetes
Readmission Risk Assistant project, applied to the Energy & Utilities
sector.

## Why this project

I built this after comparing my resume against an Energy & Utilities-sector
AI/GenAI posting that specifically asked for LangChain/RAG experience in
that domain. My existing RAG project was in healthcare — this closes the
same technical gap with real utility-regulatory source material instead.

## Data source

Six public, authoritative grid-reliability documents (205 pages total),
downloaded directly from the issuing agencies — no login or paid access
required:

| Document | Source |
|---|---|
| A More Resilient Grid (2016) | U.S. Department of Energy |
| Economic Benefits of Increasing Electric Grid Resilience to Weather Outages (2013) | U.S. Department of Energy |
| Grid Modernization Strategy (2024) | U.S. Department of Energy |
| Electric Reliability Primer | Federal Energy Regulatory Commission |
| Summer Energy Market and Electric Reliability Assessment (2025) | Federal Energy Regulatory Commission |
| Reliability Principles | North American Electric Reliability Corporation |

Raw PDFs are kept at `data/raw/`.

## Architecture

```
data/raw/                  6 source PDFs (DOE, FERC, NERC)
data/processed/chunks.jsonl   extracted + chunked text with doc/page provenance
data/processed/faiss.index    dense vector index (384-dim, all-MiniLM-L6-v2)
scripts/build_index.py     Extract (pypdf) -> chunk -> embed -> FAISS index
scripts/query_index.py     retrieval-only query utility (also used by the app)
scripts/rag_app.py         Streamlit retrieve-then-generate interface
output/index_build_log.txt    chunk counts per document from the last build
output/sample_queries.md      retrieval-quality validation (5 test questions)
```

## Pipeline

1. **Extract** — `pypdf` pulls text page-by-page from each PDF (205 pages
   with extractable text across the 6 documents).
2. **Chunk** — each page's text is split into ~900-character chunks with
   150-character overlap, producing **701 chunks**, each tagged with its
   source document and page number so every retrieval is traceable back to
   an exact page.
3. **Embed** — chunks are encoded into 384-dimension dense vectors with
   `sentence-transformers/all-MiniLM-L6-v2` and indexed in FAISS
   (`IndexFlatIP`, cosine similarity via normalized inner product).
4. **Retrieve** — a query is embedded with the same model and matched
   against the index to pull the top-k most similar chunks.
5. **Generate** — the retrieved chunks are passed as grounding context to
   an LLM (Llama-3.1-8B via the Groq API, the same model family used in my
   Diabetes Readmission Risk Assistant), which is instructed to answer
   using only that context and cite the source number for every claim.

## Retrieval-quality validation

Ran 5 representative grid-reliability questions through the index (full
results in `output/sample_queries.md`). Every top-3 retrieval landed in
the topically correct source document — grid-modernization questions
surfaced the modernization strategy document, summer-reliability questions
surfaced the FERC summer assessment, and so on — confirming the
chunking/embedding strategy separates topics cleanly even across documents
that share overlapping reliability/resilience vocabulary.

Example:

> **Q: What are NERC's core reliability principles?**
> Top match: *FERC — Electric Reliability Primer, p.53* (similarity 0.698)
> — the exact section describing NERC's role and certification as the
> Electric Reliability Organization.

## How to run

```bash
cd scripts
pip install pypdf sentence-transformers faiss-cpu streamlit groq
python3 build_index.py          # rebuilds chunks.jsonl + faiss.index from data/raw/
python3 query_index.py          # prints retrieval results for 5 test queries
streamlit run rag_app.py        # full Q&A interface
```

The Streamlit app runs in **retrieval-only mode** with zero paid
dependencies (it shows the raw retrieved passages directly). Setting a free
`GROQ_API_KEY` environment variable additionally enables LLM-generated,
citation-backed answers.

## Tech stack

Python, pypdf, sentence-transformers (embeddings), FAISS (vector search),
Streamlit (app framework), Groq API / Llama-3.1-8B (generation).
