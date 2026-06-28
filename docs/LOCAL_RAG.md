# Local / offline RAG (Phase 4.4)

Production runs `EMBEDDING_PROVIDER=gemini` with the reranker off and is unaffected
by anything here. These steps improve **local/offline** retrieval quality using a
local [Ollama](https://ollama.com) server.

## 1. bge-m3 embeddings (1024-d, stronger Vietnamese than nomic)

```bash
ollama pull bge-m3
```

Apply migration `008_add_bge_embedding` (adds the `embedding_bge` column +
`match_documents_bge` function), then point the app at bge and embed the KB:

```bash
# in backend/.env (or the environment)
EMBEDDING_PROVIDER=bge

# Embed existing KB rows that are missing the bge vector (idempotent UPDATE;
# safe to re-run). The Gemini/Jina/Ollama columns are left untouched.
python -m scripts.backfill_embeddings --provider bge
```

> A `bge` query is only ever matched against `embedding_bge` (via
> `match_documents_bge`). Until the KB is backfilled, `embedding_bge IS NULL` and
> retrieval returns nothing — run the backfill first.

The same flow works for the nomic provider: `EMBEDDING_PROVIDER=ollama` +
`python -m scripts.backfill_embeddings --provider ollama`.

## 2. Per-vector-space similarity threshold

The local providers apply a higher similarity threshold so off-target documents
are dropped (returning empty context instead of junk). Defaults:

| Provider | Threshold |
|---|---|
| ollama (nomic) | `RAG_THRESHOLD_OLLAMA=0.7` |
| bge (bge-m3) | `RAG_THRESHOLD_BGE=0.55` |
| gemini | not applied (production behavior unchanged) |

## 3. Optional offline LLM reranker

Re-rank the top candidates with the local Ollama chat model before building
context. Off by default.

```bash
RAG_RERANK_ENABLED=true
RAG_RERANK_RETRIEVE_K=8   # candidates fetched before rerank
RAG_RERANK_TOP_N=3        # kept after rerank
```

The reranker always falls back to the original vector ranking on any
error/timeout/parse failure, so enabling it can never break a response.
