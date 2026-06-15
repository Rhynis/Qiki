FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd -r gasbot \
  && useradd -r -g gasbot gasbot

COPY --from=builder /root/.local /home/gasbot/.local
ENV PATH=/home/gasbot/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
# Writable HuggingFace cache so the non-root user can download the SBERT model.
ENV HF_HOME=/home/gasbot/.cache/huggingface

COPY --chown=gasbot:gasbot . .

# The gasbot user needs a writable cache dir for the runtime model download.
# Only chown the (empty) cache dir + home entry — never the large .local tree,
# which would duplicate ~GB of deps into a new layer and bloat the image.
RUN mkdir -p /home/gasbot/.cache/huggingface \
  && chown -R gasbot:gasbot /home/gasbot/.cache \
  && chown gasbot:gasbot /home/gasbot

USER gasbot

# Use ${PORT:-8000} (shell form) so hosts that inject $PORT (Render, Oracle) work; Railway
# overrides this CMD via railway.json startCommand, so it is unaffected.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
