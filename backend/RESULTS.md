# Serving Benchmark Results

This file tracks Qiki's self-hosted vLLM (AWQ-quantized) serving story
against the API providers already in production, plus the quality cost of
quantization. See `docs/adr/0003-self-host-vllm-awq-serving.md` for the
reasoning behind self-hosting + AWQ-INT4.

**Status:** template only — no rows recorded yet. The vLLM/AWQ rows need a
real GPU run (RunPod / Kaggle / HF ZeroGPU); that's the owner's job, not
something CI or this codebase can produce (no GPU on Railway or in CI).
Ollama/Gemini/Groq rows can be filled in locally any time by pointing the
same script at those providers.

## How to regenerate

```bash
cd backend

# Serving benchmark (latency/throughput/cost) — any provider:
python -m bench.serving_benchmark --provider vllm --requests 50 --concurrency 5
python -m bench.serving_benchmark --provider ollama --requests 20
python -m bench.serving_benchmark --provider mock --requests 50   # no GPU/server needed

# Quality-after-quantization (base vs AWQ, same prompt set):
python -m bench.quality_quantization --mode vllm \
    --base-url http://gpu-host:8000/v1 --base-model Qwen/Qwen3-4B-Instruct \
    --awq-url http://gpu-host:8001/v1 --awq-model Qwen/Qwen3-4B-Instruct-AWQ
python -m bench.quality_quantization --mode mock   # no GPU/server needed
```

Both scripts **insert** a row into the tables below every time they run —
newest run first, right under the header — so the tables double as a
history log, not just a last-run snapshot. Delete rows manually to prune.

## Serving benchmark

Run vLLM, Ollama, Gemini, and Groq through the same harness and compare rows
directly — same prompt, same `--requests`/`--concurrency`, same metrics.

| Provider | Model | Requests | Concurrency | p50 (ms) | p95 (ms) | p99 (ms) | TTFT p50 (ms) | Throughput (tok/s) | Cost / 1M tok (USD) |
|---|---|---|---|---|---|---|---|---|---|
| mock | mock-model | 50 | 5 | 109 | 117 | 117 | 22 | 1142.9 | 0.0000 |

## Quality-after-quantization

Keyword-recall score (from `data/eval/rag_test_suite.json`'s
`expected_keywords`) for the base checkpoint vs its AWQ-quantized
counterpart. A negative delta means AWQ measurably hurt answer quality — the
speed win from quantization is not free, and this is the number that says
whether it was worth it.

| Base model | AWQ model | Cases | Base recall | AWQ recall | Delta |
|---|---|---|---|---|---|
| base-mock | awq-mock | 50 | 23.0% | 9.0% | -14.0% |

## Recommendations (simulated eval)

`bench/recsys_eval.py` evaluates `RecommendationService` against a SEEDED,
deterministic SIMULATED interaction log generated over the real catalog —
**not real user behavior**. Qiki has ~1 real customer and a handful of
self-test orders, nowhere near enough to evaluate a recommender against real
ground truth (see `docs/adr/0004-recommendations-thin-data.md`). The warm-session
table below is a self-consistency check ("does the ranker line up with
plausible structure"), not an accuracy claim. The cold-start table is the one
place this touches real data: precision@k against the actual best-sellers
list from real order history — reported as "N/A" honestly when there's no
order history to compare against yet.

```bash
cd backend && python -m bench.recsys_eval --simulate --seed 42
```

| Seed | Sessions | K | Recall@K | NDCG@K | MAP | Coverage |
|---|---|---|---|---|---|---|
| 42 | 300 | 5 | 80.0% | 0.601 | 0.534 | 84.2% |
| 42 | 300 | 5 | 80.0% | 0.601 | 0.534 | 84.2% |

| Seed | Sessions | K | Precision@K vs real best-sellers | Note |
|---|---|---|---|---|
| 42 | 60 | 5 | N/A | no order history yet -- cold-start precision not measurable |
| 42 | 60 | 5 | N/A | no order history yet -- cold-start precision not measurable |
