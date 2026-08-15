# Saraswat Panchang — a community calendar you can just *ask*

**Live**: https://panchang-sahapaadi.vercel.app

A chatbot (and a small companion app) built around the Saraswat Panchang — the
traditional Malayalam calendar our community uses every year for tithis,
nakshatras, festival dates, rahukalam timings, and priest/committee contacts.

## Why this exists

The printed panchang is dense. Rows and rows of tiny text, abbreviations, a grid
that only makes sense once you already know how to read it. For a lot of people in
the community — especially anyone who didn't grow up cross-referencing this exact
layout — that's a real barrier to using something that's supposed to be *for* them.

The goal here isn't a cute tech demo. It's to make the panchang genuinely easy to
use, so that when someone in the community wants to know "what's today's tithi?" or
"when's the next Ekadashi?" or "who do I call about a pooja in Kottayam?" — this is
the first place they think to check, not the last resort after squinting at the
wall calendar.

## What it actually does

Three things, all built around the same underlying data:

- **Ask Panchang** — a chat interface. Ask it about a date, a festival, today's
  tithi, or a committee contact, in plain language, and it answers from the actual
  panchang data — not a guess.
- **Monthly Pages** — the real scanned calendar pages for each month, viewable and
  zoomable, for whenever you want to see the source itself.
- **Calendar & Festivals** — a proper visual calendar grid per month, with festival
  days marked, and a tap-to-see-everything detail view for any date.

## How it works, in plain terms

### The data

Each month's panchang gets manually transcribed from the printed calendar (or a
scan of it) into a structured JSON file — one file per Malayalam month, per year.
This is genuinely hand-extracted from photos/scans, so it comes with real-world
messiness: some fields are illegible in the source and marked as such rather than
guessed, and the priest/committee-contact section has been named differently in
almost every month's file so far. The code normalizes all of that automatically,
so a new month's data — however it's shaped — just works without editing code.

### The four-layer "brain" behind the chat

Answering "what's the panchang for a given day" sounds simple, but different
questions need genuinely different strategies. So instead of routing everything
through one AI call, queries pass through layers, fastest and most certain first:

1. **Direct lookup** — exact dates, weekdays, or "today" / "tomorrow" / "yesterday".
   No AI involved at all here; it's a straight, 100%-accurate data lookup, and it's
   instant.
2. **Next-occurrence** — "when's the next Ekadashi / Pradosham?" A plain keyword
   search would just return *every* time that festival ever happened, past and
   future, with no sense of "next" — so this layer specifically sorts by date and
   picks the nearest upcoming one.
3. **Embedding + keyword search** — for open-ended or fuzzy questions that don't
   pin down an exact date. This is where "embeddings" come in: think of it as
   converting a sentence into a list of numbers that captures its *meaning*, not
   just its exact words — so "temple event" and "pooja" can match each other even
   though they share no words in common. Every day's panchang entry is pre-converted
   into one of these number-vectors, and a new question gets compared against all
   of them to find the closest meaning-matches. This runs on a small, free,
   open-source multilingual model (`intfloat/multilingual-e5-base`) entirely on the
   CPU — no paid API, and it understands Malayalam terms reasonably well, which
   matters since people naturally mix English and Malayalam when they ask. Plain
   keyword/fuzzy matching runs alongside it, because embeddings alone are bad at
   unfamiliar proper nouns and typos (a temple name spelled slightly wrong), and
   keyword search alone is bad at paraphrased questions — together they cover each
   other's blind spots.
4. **LLM generation** — once the right facts have been found by the layers above,
   an AI model turns them into an actual conversational reply, using only the
   retrieved facts (it's explicitly told not to invent tithis, dates, or events that
   aren't in front of it, and to flag anything the source data itself marked as
   uncertain). This runs on a free-tier model via OpenRouter. Being upfront about
   the trade-off: the free tier can take up to about a minute to respond under
   load, so the chat UI is honest about that with a "still thinking" message rather
   than pretending it's instant.

### The look

The visual design is pulled directly from the actual printed panchang photo — the
deep navy/maroon grid, the gold ornamental borders, the warm cream page. The chat
interface itself leans into a glass, floating aesthetic (frosted panels, softly
drifting Om/lotus/diya motifs in the background) built around saffron/orange as
the primary color, since that's the color that shows up everywhere in the
tradition this calendar comes from — the sacred flame, the tilak, the marigold.

## Under the hood

- **Backend**: Python, FastAPI. One shared module (`panchang_core.py`) holds all
  the retrieval/LLM logic, used by *both* a terminal chatbot and the web API, so
  they never drift apart from each other.
- **Embeddings**: `sentence-transformers`, running `intfloat/multilingual-e5-base`
  locally — free, private, and it works without internet once the model's cached.
- **LLM**: OpenRouter (free-tier model), swappable later without touching the rest
  of the app.
- **Frontend**: React + Vite + Tailwind CSS.
- **Data**: hand-transcribed JSON, one file per Malayalam month, normalized in code
  so year-to-year inconsistencies in the source don't require code changes.
- **Packaging**: Dockerized backend, ready to run anywhere that speaks Docker.

### Versions

| Layer | Component | Version |
|---|---|---|
| Backend | Python | 3.11 (`python:3.11-slim` base image) |
| Backend | FastAPI | 0.116.1 |
| Backend | Uvicorn | 0.48.0 |
| Backend | OpenAI SDK (OpenRouter client) | 1.77.0 |
| Backend | sentence-transformers | 5.1.1 |
| Backend | PyTorch (CPU-only build) | 2.12.0 |
| Backend | NumPy | 2.3.2 |
| Frontend | React | 19.2 |
| Frontend | Vite | 8.2 |
| Frontend | Tailwind CSS | 4.3 |
| Infra | Docker Engine | 29.1.3 (`docker.io`, Ubuntu apt) |
| Infra | Ubuntu Server (EC2) | 24.04 LTS |
| Infra | Caddy | latest stable (auto-updating apt repo) |

## Where things stand

The whole thing has moved past the demo stage: it now runs on the **complete 1202
panchang — all twelve Malayalam months, Chingam through Karkidakam** — not a
sample slice. Every feature above (chat, monthly pages, calendar & festivals) has
been tested end-to-end against this full year of real community data, with its
own reference scans and committee contacts.

**It's live.** The idea went from "wouldn't it be nice if..." to a working
product the community can actually reach — see [Live deployment](#live-deployment)
below for exactly how it's hosted.

## Live deployment

- **Frontend** — [Vercel](https://vercel.com), building from the `frontend/`
  directory (Vite production build). A single `VITE_API_BASE_URL` environment
  variable is the only thing that points it at the backend.
- **Backend** — a single AWS EC2 instance:
  - `t3.small` (2 vCPU / 2 GiB RAM), Ubuntu Server 24.04 LTS, 30 GiB gp3 EBS.
  - Runs the same Dockerized FastAPI app as local dev, unchanged — the embedding
    model stays fully self-hosted in-process, no remote inference calls.
  - A 2 GiB swap file backstops the instance's limited RAM under load.
  - [Caddy](https://caddyserver.com) reverse-proxies the container and handles
    HTTPS automatically (Let's Encrypt, auto-renewing), on a free
    [DuckDNS](https://www.duckdns.org) subdomain — a certificate needs a real
    domain, not just a bare IP.
  - An Elastic IP keeps that domain pointed at the same instance permanently,
    even across a stop/restart.
  - The container runs with `--restart unless-stopped`, so it recovers from a
    crash or an instance reboot without manual intervention.
  - Hosted within AWS's introductory account credit, with a monthly AWS Budget
    alert configured as a spend guardrail.

## What's next

- Revisit hosting costs before the AWS introductory credit runs low (roughly a
  6-month runway at current usage) — renew, resize, or move host as needed.
- Frontend polish and new UI ideas as they come up.
- Next year's panchang (1203) will land as its own sibling data folder when it's
  ready — the code is already built to pick it up with zero changes required, the
  same way it already absorbs every year-to-year naming inconsistency in the
  source data.
