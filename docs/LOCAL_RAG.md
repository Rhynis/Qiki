# Local / offline RAG (Phase 4.4)

Production runs `EMBEDDING_PROVIDER=gemini` with the reranker off and is unaffected
by anything here. These steps improve **local/offline** retrieval quality using a
local [Ollama](https://ollama.com) server.

## Provider options (pick your stack)

Two independent choices: which model **generates** the answer (`LLM_PROVIDER`) and
which model **embeds** text for retrieval (`EMBEDDING_PROVIDER`). They can be mixed.

### Generation — `LLM_PROVIDER`

| Value | Where | Model (default) | Notes |
|---|---|---|---|
| `gemini` | **Cloud** (Vertex / AI Studio) | `gemini-2.0-flash-exp` | Production default. Strongest reasoning (numbers, comparisons). Needs API/Vertex creds; per-call cost. |
| `ollama` | **Local** (your Mac) | `qwen2.5:7b-instruct-q4_K_M` | Free, private, fully offline. Weaker at numeric/price reasoning (e.g. "cheapest of 14 SKUs"); ~10–30s/answer on a Mac. |

A Groq fallback (`GROQ_API_KEY` + `GROQ_MODEL=llama-3.3-70b-versatile`) is used as a
backup generator when configured.

### Retrieval — `EMBEDDING_PROVIDER`

| Value | Where | Model / dim | Vietnamese quality | KB column |
|---|---|---|---|---|
| `gemini` | **Cloud** | `gemini-embedding-001` / 768 | strong (production) | `embedding` |
| `bge` | **Local** | `bge-m3` / 1024 | strong — ≈ gemini, best local option | `embedding_bge` |
| `ollama` | **Local** | `nomic-embed-text` / 768 | weak (compressed scores, poor threshold separation) | `embedding_ollama` |
| Jina | Cloud (auto fallback for gemini) | `jina-embeddings-v3` / 768 | strong | `embedding_jina` |

> **Vector-space rule:** a query embedded with provider X is only ever compared
> against column X. Switching providers requires the KB to be embedded for that
> provider first (see the backfill steps below), otherwise retrieval is empty.

### Common presets

| Goal | `LLM_PROVIDER` | `EMBEDDING_PROVIDER` | Cost / privacy |
|---|---|---|---|
| **Production (cloud)** | `gemini` | `gemini` | best quality; API cost; data leaves the machine |
| **Fully offline demo** | `ollama` | `bge` | $0, private, no external API; weaker generation |
| **Hybrid** | `ollama` | `gemini` | local generation + cloud-quality retrieval |

### Switching checklist

1. If local: `ollama pull <model>` (`qwen2.5:7b-instruct-q4_K_M`, `bge-m3`, `nomic-embed-text`).
2. If a new embedding space: apply its migration (`007` ollama, `008` bge).
3. Backfill the KB: `python -m scripts.backfill_embeddings --provider <gemini|ollama|bge>`.
4. Set env vars — `backend/.env` for local, Railway variables for prod.
5. Optional: per-space threshold + reranker (sections 2–3 below).

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
