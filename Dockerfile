# Backend image -- api/main.py + panchang_core.py, run with:
#   docker build -t panchang-api .
#   docker run -p 8000:8000 -e OPENROUTER_API_KEY=... panchang-api
#
# Coolify (or any Docker-based host) builds this directly from the repo root.
FROM python:3.11-slim

WORKDIR /app

# Dependencies first so this layer stays cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code and the data it serves.
COPY panchang_core.py .
COPY api/ ./api/
COPY panchang_1201/ ./panchang_1201/
COPY embeddings_cache.npz .
# Only the optimized scans the gallery actually serves -- not the raw HEIC/PDF
# originals, which would needlessly bloat the image.
COPY ["panchang images/jpegmini_optimized/", "./panchang images/jpegmini_optimized/"]

# Where the sentence-transformers model gets cached on first load. Mount this as a
# persistent volume in production so the ~1GB model download survives redeploys
# instead of re-fetching every time the container is rebuilt.
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface

# Comma-separated list of origins allowed to call the API -- set this to your real
# frontend URL(s) in production; defaults to common local-dev ports.
ENV ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
ENV PORT=8000

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
