# Backend image for Hugging Face Spaces (Docker SDK) -- see README.md for the Space
# config block. Spaces run the container as a non-root user and only guarantee /tmp
# as writable at runtime, and free-tier Spaces sleep after inactivity -- so the
# embedding model is downloaded and cached INTO the image at build time (while the
# builder has normal network/write access), and the container runs fully offline
# after that. This means a cold wake-up only pays for loading the model from local
# disk, never a ~1GB re-download.
FROM python:3.11-slim

# Spaces convention: a non-root user with a real home directory.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Dependencies first so this layer stays cached across code-only changes.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Application code and the data it serves.
COPY --chown=user panchang_core.py .
COPY --chown=user api/ ./api/
COPY --chown=user panchang_1202/ ./panchang_1202/
COPY --chown=user embeddings_cache.npz .
# Only the optimized scans the gallery actually serves -- not the raw HEIC/PDF
# originals, which would needlessly bloat the image.
COPY --chown=user ["panchang images/jpegmini_optimized/", "./panchang images/jpegmini_optimized/"]

# Bake the embedding model into the image now, while the network is available and
# the cache dir is writable.
ENV HF_HOME=$HOME/app/.cache/huggingface
# WORKDIR above is created by Docker as root regardless of the active USER -- a
# long-standing Docker quirk -- so `user` can't create .cache under it on its own.
# Fix that ownership explicitly before the download runs as `user` below.
USER root
RUN mkdir -p $HF_HOME && chown -R user:user $HOME/app/.cache
USER user
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

# From here on, no network/model-registry calls at runtime -- everything needed is
# already on disk from the build step above.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Comma-separated list of origins allowed to call the API -- set this to your real
# Vercel frontend URL via the Space's "Variables and secrets" settings; defaults to
# common local-dev ports so it still runs standalone without that configured.
ENV ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
# 7860 is Hugging Face Spaces' standard Docker SDK port (see README.md's app_port).
ENV PORT=7860

EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
