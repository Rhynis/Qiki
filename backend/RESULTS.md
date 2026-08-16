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
