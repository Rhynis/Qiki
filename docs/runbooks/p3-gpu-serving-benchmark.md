# Runbook — P3 serving benchmark on a GPU (real numbers for `RESULTS.md`)

The vLLM provider (`app/llm/providers/vllm_provider.py`) and the two harnesses
(`backend/bench/serving_benchmark.py`, `backend/bench/quality_quantization.py`) are
already in the repo and CI-tested with `--provider mock` / `--mode mock`. What they
**cannot** produce without a GPU are the real numbers — p95/throughput/VRAM/cost and
the quantization quality delta. This runbook fills that gap: run it once on a free GPU
and paste the printed rows into `backend/RESULTS.md`.

> **Never hand-write numbers into `RESULTS.md`.** The whole point (and the honest
> interview answer) is that they were measured. If you didn't run it, leave it as the
> template.

## Where to run it (free GPU)

- **Kaggle Notebook** — Settings → Accelerator → **GPU T4 ×2**, 30 h/week free. Easiest.
- **Google Colab** (T4) or **RunPod** ($10 trial ≈ 29 h RTX 4090) also work.

## Steps (Kaggle cells)

```bash
# Cell 1 — clone + install (vllm needs the GPU image; the rest is the backend's deps)
!git clone https://github.com/Rhynis/Qiki.git
!cd Qiki/backend && pip install -q -r requirements.txt vllm
```

```python
# Cell 2 — serve a quantized (AWQ) model with vLLM and wait until it's ready.
# Use a pre-quantized AWQ checkpoint from HuggingFace so you skip the heavy
# quantization step. Swap MODEL_AWQ for whichever Vietnamese-capable AWQ model
# you want to report on (e.g. a Qwen AWQ build, or GreenNode GreenMind if an AWQ
# build exists). Keep the same string in VLLM_MODEL in Cell 3.
import subprocess, time, requests
MODEL_AWQ = "Qwen/Qwen2.5-3B-Instruct-AWQ"   # <-- change to your target AWQ model
subprocess.Popen([
    "python", "-m", "vllm.entrypoints.openai.api_server",
    "--model", MODEL_AWQ, "--quantization", "awq",
    "--port", "8000", "--max-model-len", "4096",
])
for _ in range(60):
    try:
        requests.get("http://localhost:8000/v1/models", timeout=2)
        print("vLLM ready"); break
    except Exception:
        time.sleep(10)
```

```bash
# Cell 3 — REAL serving benchmark (p50/p95/p99 latency, throughput, TTFT, cost).
# Writes/append the row to RESULTS.md and prints it.
%cd /kaggle/working/Qiki/backend
!VLLM_BASE_URL=http://localhost:8000/v1 VLLM_MODEL=$MODEL_AWQ \
  python -m bench.serving_benchmark --provider vllm --requests 50 --concurrency 5
```

To make the comparison table (the interesting part), run the SAME harness against the
other engines and let it append more rows:

```bash
# Ollama (install + pull first if you want a CPU/GPU local baseline)
!python -m bench.serving_benchmark --provider ollama --requests 20
# API providers (uses your keys via env; small request count to stay in free quota)
!GEMINI_API_KEY=... python -m bench.serving_benchmark --provider gemini --requests 20
!GROQ_API_KEY=...   python -m bench.serving_benchmark --provider groq   --requests 20
```

```bash
# Cell 4 — quantization quality delta (base vs AWQ) on a Vietnamese prompt set.
# Serve the FULL (unquantized) model on a second port, then compare. If VRAM is
# tight on one GPU, do it sequentially: run Cell 3 (AWQ), stop that server, serve
# the base model on :8001, then run this.
!python -m bench.quality_quantization --mode vllm \
  --base-url http://localhost:8001/v1 --base-model Qwen/Qwen2.5-3B-Instruct \
  --awq-url  http://localhost:8000/v1 --awq-model $MODEL_AWQ
```

## After the run

1. Copy every printed `RESULTS.md` table row into `backend/RESULTS.md` (replace the
   "template only — no rows recorded yet" note).
2. Commit on a branch + PR (e.g. `data/p3-benchmark-results`) so the numbers are
   code-tracked. Do NOT edit the numbers afterwards.
3. Turn them into CV bullets **with the real figures** — e.g. "vLLM AWQ-INT4 Qwen: p95
   ___ ms at ___ tok/s, ___% VRAM vs FP16, VMLU drop ___ points."

## Notes / gotchas

- vLLM requires **NVIDIA CUDA** — it does not run on a Mac (Apple Silicon) or CPU-only
  host. That is why this is a GPU-host runbook, not something the app or CI runs.
- Production (Railway, CPU/free-tier) stays on the API providers; vLLM is a
  benchmark/demo layer (see `docs/adr/0003-self-host-vllm-awq-serving.md`).
- Report latency/throughput **honestly**, including if AWQ hurts quality — the
  trade-off IS the story.
