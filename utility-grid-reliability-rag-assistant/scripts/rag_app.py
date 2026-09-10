"""
Utility Grid Reliability RAG Assistant — Streamlit app
Retrieve-then-generate: pulls the most relevant passages from 6 public
DOE/FERC/NERC grid-reliability documents (via query_index.retrieve) and
asks an LLM (Llama-3.1-8B via the Groq API, same model family used in the
Diabetes Readmission Risk Assistant project) to answer using only that
retrieved context, with every claim citation-backed to a source document
and page number.

Run: streamlit run rag_app.py
Requires a free Groq API key exported as GROQ_API_KEY. Without a key, the
app still runs in retrieval-only mode (shows the source passages directly)
so the pipeline is demonstrable with zero paid dependencies.
"""
import os
import streamlit as st
from query_index import retrieve

st.set_page_config(page_title="Utility Grid Reliability RAG Assistant", page_icon="⚡")
st.title("⚡ Utility Grid Reliability RAG Assistant")
st.caption("Retrieval-augmented Q&A over DOE, FERC, and NERC public grid-reliability "
           "documents — every answer is grounded and citation-backed, not the model's "
           "own recollection.")

with st.sidebar:
    st.markdown("### Source corpus")
    st.markdown("""
- DOE — A More Resilient Grid (2016)
- DOE — Economic Benefits of Increasing Electric Grid Resilience (2013)
- DOE — Grid Modernization Strategy (2024)
- FERC — Electric Reliability Primer
- FERC — Summer Energy Market & Electric Reliability Assessment (2025)
- NERC — Reliability Principles
    """)
    st.markdown("701 chunks · 384-dim embeddings (all-MiniLM-L6-v2) · FAISS index")

query = st.text_input("Ask a question about grid reliability, resilience, or modernization:",
                       placeholder="e.g. How does the grid prepare for summer peak demand?")

if query:
    with st.spinner("Retrieving relevant passages..."):
        results = retrieve(query, k=4)

    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        from groq import Groq
        client = Groq(api_key=api_key)
        context = "\n\n".join(
            f"[Source {i+1}: {r['doc']}, p.{r['page']}]\n{r['text']}"
            for i, r in enumerate(results))
        prompt = (
            "Answer the question using ONLY the numbered sources below. "
            "Cite the source number for every claim. If the sources don't "
            "contain the answer, say so explicitly.\n\n"
            f"{context}\n\nQuestion: {query}\nAnswer:"
        )
        with st.spinner("Generating answer..."):
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        st.markdown("### Answer")
        st.write(completion.choices[0].message.content)
    else:
        st.info("No GROQ_API_KEY set — showing retrieved source passages directly "
                "(retrieval-only mode). Set the environment variable to enable "
                "LLM-generated, citation-backed answers.")

    st.markdown("### Retrieved sources")
    for i, r in enumerate(results):
        with st.expander(f"[{i+1}] {r['doc']} — p.{r['page']}  (similarity {r['score']:.3f})"):
            st.write(r["text"])
