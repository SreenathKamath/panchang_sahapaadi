"""
Panchang web API
------------------
FastAPI wrapper around panchang_core.py's ChatState/answer_query, plus endpoints for
the calendar (special-notes) view and the scanned reference calendar images. This is
a thin HTTP surface -- all retrieval/LLM logic lives in panchang_core.py, shared with
the CLI in panchang_chatbot.py, so the two never drift apart.

Run from the project root (so `panchang_core` resolves):
    uvicorn api.main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from panchang_core import ChatState, IMAGES_DIR, answer_query, month_days, month_summaries

state: ChatState | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Loading the JSON data, the embedding model, and building/loading the embeddings
    # cache takes real time (first run especially) -- do it once at startup, not
    # per-request.
    global state
    state = ChatState()
    yield


app = FastAPI(title="Panchang API", lifespan=lifespan)

# Comma-separated list of allowed origins, e.g. "https://panchang.vercel.app" in
# production -- read from the environment (see Dockerfile/deployment config) rather
# than hardcoded, so pointing this at a new frontend domain is a config change, not a
# code change. Defaults to the local Vite dev server ports when unset.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scanned reference calendar pages (1201_1.jpg, 1201_2.jpg, ...), served straight from
# the existing folder rather than duplicated into the frontend build.
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


class ChatRequest(BaseModel):
    query: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "loaded_months": state.loaded_months_label,
        "loaded_range": state.loaded_range,
        "document_count": len(state.docs),
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    try:
        result = answer_query(state, query)
    except Exception:
        # An unhandled exception here would otherwise escape FastAPI's exception
        # middleware and hit Starlette's outer error handler, which sits OUTSIDE
        # CORSMiddleware -- the resulting response has no Access-Control-Allow-Origin
        # header, so the browser blocks it and the frontend sees a generic
        # "Failed to fetch" instead of the real error (hit in production 2026-08-22
        # when OpenRouter pulled the pinned free model). Raising HTTPException keeps
        # the response inside CORS middleware's wrapping.
        logging.exception("answer_query failed for query=%r", query)
        raise HTTPException(
            status_code=503,
            detail="The Panchang assistant is temporarily unavailable. Please try again in a moment.",
        )

    if result["status"] == "answered":
        return {
            "status": "answered",
            "reply": result["reply"],
            "match_source": result["match_source"],
            "sources": [
                {"gregorian_date": d["gregorian_date"], "malayalam_month": d.get("malayalam_month")}
                for d in result["matches"]
            ],
        }
    return result  # ambiguous / date_not_covered / not_found -- already JSON-shaped


@app.get("/api/months")
def months():
    return month_summaries(state.datasets)


@app.get("/api/months/{month_name}/days")
def days(month_name: str):
    result = month_days(state.datasets, month_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Month '{month_name}' is not loaded")
    return result
