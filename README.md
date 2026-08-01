---
title: Saraswat Panchang API
emoji: 🪔
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

Backend API for the Saraswat Panchang chatbot (retrieval + LLM logic in
`panchang_core.py`, exposed via FastAPI in `api/main.py`). The actual chat/gallery/
calendar interface lives in `frontend/` and is deployed separately (Vercel); this
Space only serves the API and the scanned reference images it depends on.

Endpoints: `/api/health`, `/api/chat`, `/api/months`, `/api/months/{name}/days`,
`/images/*`.

Requires an `OPENROUTER_API_KEY` secret set in this Space's settings, and
`ALLOWED_ORIGINS` set to the deployed frontend's URL once it exists.
