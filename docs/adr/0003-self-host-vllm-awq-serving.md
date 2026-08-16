# ADR-0003: Self-hosted vLLM + AWQ-INT4 serving, as a benchmark/demo layer

## Status

Accepted

## Context

Qiki's production LLM traffic runs entirely on API providers today —
Gemini primary, Groq (and each other) as failover, Ollama for local dev and
the offline demo mode (see `docs/adr/0001-langgraph-agent-orchestration.md`
and the local-demo-mode work, issue #227). That's the right call for a
single-tenant chatbot with modest volume: no ops burden, no GPU bill, and
API providers' own infra scales far past what this project needs.

It is, however, a gap for the parts of the portfolio story this project is
also meant to demonstrate — the JDs this codebase is built against (banking,
GMO-Z.com, NVIDIA-adjacent roles) routinely ask about **self-hosted
inference**: running an open-weight model on owned/rented GPU hardware,
quantizing it to fit a smaller card and serve faster, and being able to
reason concretely about the cost/latency/quality trade-offs of doing so
instead of just calling an API. Two concrete drivers for a self-hosted
option, even if this app never runs on one 24/7:

1. **Cost at volume.** API pricing is per-token and scales linearly with
   traffic; a rented GPU is a fixed hourly cost that amortizes down as
   throughput goes up. Past some request volume, self-hosting is cheaper —
   the "Recorded runs" log in `RESULTS.md` is exactly the tool for finding
   that crossover point for a given GPU rate.
2. **Data residency / air-gapping.** Banking and healthcare deployments
   frequently cannot send prompts to a third-party API at all, regardless of
   cost — the model has to run inside a network boundary the operator
   controls. A self-hosted serving layer is the only way to satisfy that
   constraint, and being able to stand one up (quantized to fit affordable
   hardware) is the actual skill being demonstrated here.

Also relevant: this app has **no GPU anywhere in its real deployment path**.
Railway (prod) and GitHub Actions (CI) are both CPU-only. Whatever gets built
here has to be honest about that instead of pretending vLLM is a drop-in
prod replacement.

## Decision

Add a **self-hosted vLLM provider** (`VLLMProvider`, an OpenAI-compatible
HTTP client — see `backend/app/llm/providers/vllm_provider.py`) that plugs
into the existing `LLMProviderFactory` / `FallbackLLMProvider` exactly like
Gemini, Groq, and Ollama do, selected via `LLM_PROVIDER=vllm`. Ship it as a
**benchmark/demo layer**:

- The provider code, the Docker Compose `serving` profile, the benchmark
  harness (`bench/serving_benchmark.py`), and the quality-after-quantization
  harness (`bench/quality_quantization.py`) all live in this codebase and are
  fully exercised in CI (against a mock provider — no GPU required).
- **The actual GPU run** — quantizing a model to AWQ-INT4, standing up vLLM
  on a rented GPU, and filling `RESULTS.md` with real numbers — is the
  owner's job, done manually against RunPod / Kaggle / HF ZeroGPU. Nothing in
  CI or Railway ever installs `vllm` (see "Dependency isolation" below).
- Production stays on the existing API providers unconditionally.
  `LLM_PROVIDER`'s default is unchanged; nothing about this ADR changes
  behavior for anyone who doesn't explicitly opt in.

### Engine choice: vLLM over SGLang or Ollama

| Engine | Why not (for this role) |
|---|---|
| **Ollama** | Already used here for local dev — but it's a llama.cpp-based single-request-at-a-time server tuned for convenience, not throughput. It doesn't expose the continuous-batching / paged-attention internals that make a serving benchmark interesting, and its quantization story (GGUF) is a different technique than AWQ/GPTQ, which is what production serving stacks (and the JDs this targets) actually ask about. |
| **SGLang** | A legitimate competitor to vLLM with a comparable feature set (paged attention, continuous batching, several quantization formats) and, on some workloads, better numbers. It's a reasonable choice; vLLM was picked instead for being the more widely adopted default with the larger ecosystem (broadest model/quantization support, most examples to cite in an interview, most likely to be what an interviewer has already used) — not because SGLang is worse. |
| **vLLM (chosen)** | PagedAttention + continuous batching for real throughput under concurrent load, first-class AWQ/GPTQ/FP8 quantization support, and an OpenAI-compatible server out of the box — meaning `VLLMProvider` needed zero protocol invention, just the same httpx pattern `GroqProvider` already uses against a different `base_url`. |

### Quantization: AWQ-INT4 over GPTQ

| Format | Trade-off |
|---|---|
| **GPTQ** | Mature, widely supported, but its calibration process (layer-by-layer reconstruction via a calibration set) is slower to produce and has historically been more sensitive to calibration-data quality — a bad calibration set can quietly tank accuracy in ways that are easy to miss without an eval harness. |
| **AWQ (chosen)** | Activation-aware — it protects the small fraction of weight channels that matter most for activation magnitude instead of quantizing everything uniformly, which tends to preserve accuracy better at INT4 than naive uniform quantization, at a calibration cost that's cheaper to run than GPTQ's. vLLM has first-class AWQ kernel support, so there's no throughput penalty for choosing it. |
| **INT4 over INT8** | INT8 is the safer, smaller quality hit; INT4 roughly halves VRAM and increases throughput further, at real quality risk. The whole reason `bench/quality_quantization.py` exists is to not take that risk on faith — the ADR's answer is "INT4, but prove it" via the keyword-recall delta on the existing RAG eval golden set, not "INT4 because it's smaller." |

### Dependency isolation

`vllm` pulls in a CUDA-specific PyTorch build — multiple hundred MB, and
simply uninstallable on a CPU-only CI runner or Railway's containers. It is
pinned **only** in `backend/requirements-serving.txt`, which neither
`requirements.txt` nor `requirements-dev.txt` reference. `pip install -r
requirements.txt -r requirements-dev.txt` (what CI and Railway both run)
never sees it. `VLLMProvider` itself has no import-time dependency on the
`vllm` package at all — it's a plain `httpx` client against vLLM's server,
the same relationship `GroqProvider` has to Groq's API.

### Failover behavior: extending `FallbackLLMProvider`

Every existing fallback chain (`gemini` <-> `groq`) only fails over on
`LLMQuotaExceededError` / `LLMRateLimitError` — a hosted API's dominant
failure mode. A self-hosted box's dominant failure mode is different: it's
down, unreachable, or the process crashed (`LLMConnectionError` /
`LLMTimeoutError`), which the existing chain would *not* fail over on. Rather
than special-case vLLM outside `FallbackLLMProvider`, it gained one
backward-compatible constructor parameter, `extra_fallback_errors` (default
`()`, so every existing chain's behavior is byte-for-byte unchanged) —
`factory.py`'s `vllm` branch is the only caller that passes a non-empty
value.

## Honest limitations

- **No GPU in this project's real deployment.** Railway (prod) and CI both
  run CPU-only. `LLM_PROVIDER=vllm` is not something this app's actual
  deployment can turn on — it's a local/rented-GPU demo path, full stop. The
  Docker Compose `vllm` service documents this (`profiles: ["serving"]`,
  requires an NVIDIA GPU reservation) rather than pretending otherwise.
- **`RESULTS.md`'s vLLM/AWQ numbers are not filled in by this PR.** They
  require an actual GPU run, which is out of scope here by design (see the
  issue's own scope split) — this PR ships the harness and a template, not
  fabricated numbers.
- **The quality harness's mock mode proves the code path, not real quality
  loss.** `bench/quality_quantization.py --mode mock` exercises the
  keyword-recall scoring and delta computation deterministically in CI, but
  the two mock responses are hand-written to differ, not measured off a real
  base-vs-AWQ pair. The number that matters (does AWQ measurably hurt answer
  quality on Qiki's actual RAG eval set) only exists after a real GPU run.
- **Keyword recall is a proxy, not a real quality metric.** It reuses
  `expected_keywords` from the existing RAG eval golden set
  (`data/eval/rag_test_suite.json`) because it's already there and requires
  no new labeling — it is not RAGAS/VMLU-grade evaluation. Good enough to
  catch a gross regression (e.g. AWQ dropping the price or size entirely from
  an answer); not a substitute for a real VMLU/VLSP benchmark run if the
  owner wants a stronger accuracy claim.
