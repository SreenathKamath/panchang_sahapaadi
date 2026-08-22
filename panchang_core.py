"""
Panchang RAG core
------------------
Shared data loading, retrieval, and LLM logic for the Saraswat Panchang chatbot.
Both the CLI (panchang_chatbot.py) and the web API (api/main.py) import from here --
this is the single source of truth for how a query gets answered, so the two surfaces
never drift apart.

Architecture:
1. Direct lookup layer   -> exact date / weekday / sunrise-sunset queries, including
                             "today"/"tomorrow"/"yesterday" (fast, 100% accurate, no
                             embeddings needed)
2. Next-occurrence layer -> "when's the next Ekadashi/Pradosham" -- keyword search
                             sorted by date, preferring today-or-later
3. Embedding retrieval   -> open-ended / fuzzy questions
                             (local multilingual model, free, offline)
4. LLM generation        -> OpenRouter chat completion turns retrieved
                             facts into a natural-language reply
"""

import logging
import os
import re
import json
import difflib
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# ---------------- Config ----------------
PROJECT_ROOT = Path(__file__).parent
# Scoped to this year's folder on purpose -- next year's data will arrive as a sibling
# folder (e.g. panchang_1203/) with its own JSON_GLOB, not dropped in here.
DATA_DIR = PROJECT_ROOT / "panchang_1202"
JSON_GLOB = "panchang_*.json"   # every month file in DATA_DIR is auto-discovered, nothing to edit per month
IMAGES_DIR = PROJECT_ROOT / "panchang images" / "jpegmini_optimized"
EMBED_CACHE_PATH = PROJECT_ROOT / "embeddings_cache.npz"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"   # good Malayalam support, runs on CPU
# Tried in order, falling through to the next on ANY error -- OpenRouter's free tier
# is volatile: models get rate-limited under shared-pool load (429), pulled from free
# entirely (404, hit with openai/gpt-oss-20b:free on 2026-08-22), or are flaky in other
# ways. Deliberately explicit models, never "openrouter/free" -- that auto-router can
# land on a non-chat model (e.g. nvidia/nemotron-3.5-content-safety:free, a moderation
# classifier, not an assistant). Nemotron entries are last-resort: confirmed working,
# but the "-nano-"/"-super-" reasoning ones sometimes leak their reasoning into the
# reply itself (e.g. "User asks: ... They want the assistant to...") instead of a
# clean answer -- worth re-checking OpenRouter's free model list periodically and
# promoting whichever is currently most reliable.
LLM_MODELS = [
    "google/gemma-4-26b-a4b-it:free",   # Google AI Studio
    "z-ai/glm-5.2:free",                 # Z.ai -- different provider, so a Google-wide
                                          # outage (both gemma entries share this pool,
                                          # confirmed 2026-08-22) only costs one wasted
                                          # call before landing here, not two
    "google/gemma-4-31b-it:free",        # Google AI Studio, same pool as the first entry
    "nvidia/nemotron-3-nano-30b-a3b:free",
]
TOP_K = 3
SIM_THRESHOLD = 0.55   # below this, we tell the user we're not confident rather than guess

# Standard Malayalam calendar (Kollavarsham) month order, Chingam first -- used to map
# a month name to its position in the year, which is how the scanned reference images
# are named (e.g. "1201_1.jpg" = year 1201, 1st month = Chingam).
MALAYALAM_MONTH_ORDER = [
    "chingam", "kanni", "thulam", "vrischikam", "dhanu", "makaram",
    "kumbham", "meenam", "medam", "edavam", "mithunam", "karkidakam",
]

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


# ---------------- Data loading ----------------
def load_all_data(data_dir: Path = DATA_DIR, pattern: str = JSON_GLOB) -> list[dict]:
    """Loads every panchang month file matching the glob -- add a new month's JSON
    next to this script and it's included with no code changes."""
    paths = sorted(data_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No panchang data files found matching '{pattern}' in {data_dir}")

    datasets = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            datasets.append(json.load(f))

    # Filenames sort alphabetically (chingam, dhanu, edavam, kanni, ...), not
    # chronologically -- that happened to match for a 3-month demo (chingam, kanni,
    # thulam) but silently scrambles month order once a full 12-month year is loaded.
    # Sorting by each month's first day's actual date is unambiguous regardless of
    # spelling/ordering conventions in the source JSON.
    datasets.sort(key=lambda d: d["days"][0]["gregorian_date"])
    return datasets


def collect_month_names(datasets: list[dict]) -> list[str]:
    """Derives the set of Malayalam month names actually present in the loaded data,
    so the date regex and stopwords never have a month name hardcoded into them."""
    names = []
    for data in datasets:
        name = data.get("panchang_month", {}).get("malayalam_month")
        if name and name.strip().lower() not in names:
            names.append(name.strip().lower())
    return names


def month_image_filename(month_info: dict) -> str | None:
    """Maps a month's JSON to its scanned reference image filename (e.g. "1201_1.jpg"),
    using MALAYALAM_MONTH_ORDER to work out its position in the year. Returns None
    instead of raising if the month name or image file isn't recognized/present, so a
    missing scan for some future month never breaks the rest of the app."""
    name = (month_info.get("malayalam_month") or "").strip().lower()
    year = month_info.get("malayalam_month_number")
    if name not in MALAYALAM_MONTH_ORDER or year is None:
        return None
    index = MALAYALAM_MONTH_ORDER.index(name) + 1
    filename = f"{year}_{index}.jpg"
    return filename if (IMAGES_DIR / filename).exists() else None


def nearest_sunrise_sunset(sunrise_table: list, malayalam_date: int) -> dict | None:
    """The sunrise/sunset table is sparse (only some dates listed). Sunrise/sunset
    shifts by seconds per day, so using the closest earlier entry is accurate enough."""
    candidates = [e for e in sunrise_table if e["malayalam_date"] <= malayalam_date]
    if not candidates:
        return sunrise_table[0] if sunrise_table else None
    return max(candidates, key=lambda e: e["malayalam_date"])


def describe_panchang_field(field: dict, label: str) -> str:
    """Several days per month have a null name (scan cell was illegible) and some
    non-null fields carry a 'confidence: low' marker from the extraction pass. Naively
    interpolating these into text produced literal 'the tithi is None' -- this instead
    surfaces both cases honestly so the LLM (and the user) knows when a reading is
    missing or uncertain rather than silently treating it as fact."""
    name = field.get("name")
    if name is None:
        return f"{label} is not confidently recorded in the source scan"

    end_time = field.get("end_time")
    tail = f" (ending around {end_time})" if end_time else ""

    confidence = field.get("confidence")
    uncertain = " (uncertain reading)" if confidence and str(confidence).lower().startswith("low") else ""

    return f"{label} is {name}{tail}{uncertain}"


def day_to_text(day: dict, month_info: dict) -> str:
    """Turns one day's structured JSON into a natural-language paragraph.
    This is what actually gets embedded -- raw JSON embeds poorly."""
    sunrise_entry = nearest_sunrise_sunset(
        month_info.get("sunrise_sunset_table", []), day["malayalam_date"]
    )
    sun_text = ""
    if sunrise_entry:
        sun_text = (
            f" Sunrise is around {sunrise_entry['udayam']} and "
            f"sunset is around {sunrise_entry['astamayam']}."
        )

    notes = day.get("special_notes") or []
    notes_text = " ".join(notes) if notes else "No special festival or event is noted for this day."

    moon = day.get("moon_phase_marker")
    moon_text = f" This day is marked as {moon}." if moon else ""

    text = (
        f"On {day['weekday']} ({day['gregorian_date']}, "
        f"Malayalam calendar date {day['malayalam_date']} of "
        f"{month_info.get('malayalam_month', '')} {month_info.get('malayalam_month_number', '')}), "
        f"{describe_panchang_field(day['tithi'], 'the tithi')}, "
        f"{describe_panchang_field(day['nakshatra'], 'nakshatra')}, "
        f"{describe_panchang_field(day['yoga'], 'yoga')}, and "
        f"{describe_panchang_field(day['karana'], 'karana')}. "
        f"Rahukalam is {day['rahukalam']} and Gulikakalam is {day['gulikakalam']}."
        f"{sun_text} {notes_text}{moon_text}"
    )
    return text


COMMITTEE_ROLE_LABELS = {
    "advisors": "Advisor",
    "ganitham_astronomical_calculation": "Ganitham (Astronomical Calculation)",
    "committee_members": "Committee Member",
}


def normalize_committee(month_info: dict) -> list[dict]:
    """Each of the three loaded months named its priest/committee-contact block
    differently -- 'vedic_sabha_committee' (flat list, each entry has its own role),
    'advisors_and_calculation_committee' (a dict of two sub-lists, no per-entry role),
    and 'committee_members' (flat list, no role). Rather than requiring next year's
    JSON to match one exact key/shape, this pulls every name/area/phone entry out of
    any key that mentions 'committee' or 'advisor', regardless of nesting -- so a
    fourth naming variant next year still surfaces without a code change."""
    entries = []
    for key, value in month_info.items():
        if "committee" not in key and "advisor" not in key:
            continue
        groups = value.items() if isinstance(value, dict) else [(key, value)]
        for subkey, sublist in groups:
            if not isinstance(sublist, list):
                continue
            role_label = COMMITTEE_ROLE_LABELS.get(subkey, subkey.replace("_", " ").title())
            for e in sublist:
                if isinstance(e, dict) and e.get("name"):
                    entries.append({
                        "role": e.get("role") or role_label,
                        "name": e["name"],
                        "area": e.get("area"),
                        "phone": e.get("phone"),
                    })
    return entries


def build_documents(datasets: list[dict]) -> list[dict]:
    docs = []
    for data in datasets:
        month_info = data["panchang_month"]
        month_name = month_info.get("malayalam_month")

        for day in data["days"]:
            docs.append({
                "malayalam_date": day["malayalam_date"],
                "gregorian_date": day["gregorian_date"],
                "weekday": day["weekday"],
                "malayalam_month": month_name,
                "text": day_to_text(day, month_info),
                "raw": day,
            })

        # One extra document per month for month-level questions (samvatsaram, saka varsham, etc.)
        overview = (
            f"This panchang covers {month_name} "
            f"({month_info.get('malayalam_month_number')}), Saka varsham "
            f"{month_info.get('saka_varsham')}, {month_info.get('samvatsaram')} samvatsaram, "
            f"corresponding to the Gregorian range {month_info.get('gregorian_range')}. "
            f"This spans {month_info.get('malayalam_month_span', '')}."
        )
        if month_info.get("footer_note"):
            overview += f" Note: {month_info['footer_note']}."
        docs.append({
            "malayalam_date": None,
            "gregorian_date": None,
            "weekday": None,
            "malayalam_month": month_name,
            "text": overview,
            "raw": {"type": "month_overview", **month_info},
        })

        # One document per committee/priest contact so "who is the purohit for
        # <area>" or "phone number for <area>" style questions are answerable.
        for entry in normalize_committee(month_info):
            area_text = f" for {entry['area']}" if entry.get("area") else ""
            phone_text = f" Contact phone: {entry['phone']}." if entry.get("phone") else ""
            docs.append({
                "malayalam_date": None,
                "gregorian_date": None,
                "weekday": None,
                "malayalam_month": month_name,
                "text": (
                    f"{entry['role']} {entry['name']} is a panchang committee/priest "
                    f"contact{area_text}, listed in the {month_name} "
                    f"({month_info.get('malayalam_month_number')}) panchang.{phone_text}"
                ),
                "raw": {"type": "committee_member", **entry},
            })

        # One document per month summarizing planetary transit notes, when present.
        # These are flagged low-confidence in the source extraction (unclear
        # abbreviations), so the text carries that caveat rather than stating
        # transit timing as settled fact.
        planets = month_info.get("planetary_positions") or []
        if planets:
            planet_lines = "; ".join(
                f"{p['planet']} noted around malayalam date {p['malayalam_date']} ({p.get('raw_text', '')})"
                for p in planets
            )
            docs.append({
                "malayalam_date": None,
                "gregorian_date": None,
                "weekday": None,
                "malayalam_month": month_name,
                "text": (
                    f"Planetary transit notes for {month_name}: {planet_lines}. "
                    f"These are low-confidence extractions from the source scan -- "
                    f"treat exact transit timing as approximate and verify against the printed panchang."
                ),
                "raw": {"type": "planetary_positions", "entries": planets},
            })
    return docs


# ---------------- Calendar-view helpers (for the frontend's day-by-day view) ----------------
def month_summaries(datasets: list[dict]) -> list[dict]:
    """One lightweight summary per loaded month, in the order they're loaded (already
    chronological -- see load_all_data's sorted glob), for a month picker / overview UI."""
    summaries = []
    for data in datasets:
        month_info = data["panchang_month"]
        summaries.append({
            "malayalam_month": month_info.get("malayalam_month"),
            "malayalam_month_number": month_info.get("malayalam_month_number"),
            "malayalam_month_span": month_info.get("malayalam_month_span"),
            "saka_varsham": month_info.get("saka_varsham"),
            "samvatsaram": month_info.get("samvatsaram"),
            "gregorian_range": month_info.get("gregorian_range"),
            "footer_note": month_info.get("footer_note"),
            "image": month_image_filename(month_info),
            "day_count": len(data["days"]),
        })
    return summaries


def month_days(datasets: list[dict], month_name: str) -> list[dict] | None:
    """Full day-by-day list for one month (by malayalam_month name, case-insensitive),
    for the calendar/special-notes view. Returns None if the month isn't loaded."""
    month_name = month_name.strip().lower()
    for data in datasets:
        month_info = data["panchang_month"]
        if (month_info.get("malayalam_month") or "").strip().lower() != month_name:
            continue
        return [
            {
                "malayalam_date": day["malayalam_date"],
                "gregorian_date": day["gregorian_date"],
                "weekday": day["weekday"],
                "tithi": day["tithi"].get("name"),
                "nakshatra": day["nakshatra"].get("name"),
                "rahukalam": day["rahukalam"],
                "gulikakalam": day["gulikakalam"],
                "highlighted": day.get("highlighted", False),
                "moon_phase_marker": day.get("moon_phase_marker"),
                "special_notes": day.get("special_notes") or [],
            }
            for day in data["days"]
        ]
    return None


# ---------------- Embeddings ----------------
def get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL_NAME)


def build_or_load_embeddings(docs: list[dict]):
    texts = [d["text"] for d in docs]

    if EMBED_CACHE_PATH.exists():
        cached = np.load(EMBED_CACHE_PATH, allow_pickle=True)
        if list(cached["texts"]) == texts:
            return cached["embeddings"]

    print("Building embeddings (first run only, cached after this)...")
    model = get_embedder()
    # e5 models expect a "passage: " prefix for documents being indexed
    prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=True)
    np.savez(EMBED_CACHE_PATH, embeddings=embeddings, texts=np.array(texts, dtype=object))
    return embeddings


def embed_query(query: str, model) -> np.ndarray:
    # e5 models expect a "query: " prefix for search queries
    return model.encode([f"query: {query}"], normalize_embeddings=True)[0]


def cosine_top_k(query_vec: np.ndarray, doc_vecs: np.ndarray, k: int):
    sims = doc_vecs @ query_vec  # vectors already normalized -> dot product = cosine sim
    top_idx = np.argsort(sims)[::-1][:k]
    return [(int(i), float(sims[i])) for i in top_idx]


# ---------------- Direct lookup layer ----------------
GREGORIAN_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

WEEKDAYS = ["ravivaram", "chandravaram", "kujavaram", "budhavaram",
            "guruvaram", "sukravaram", "mandavaram"]

# "What's today's panchang" is the single most common real-world question a community
# member will ask, and it can't be phrased as a literal YYYY-MM-DD -- so it gets its own
# resolver rather than requiring the user to know today's Gregorian date.
RELATIVE_DATE_OFFSETS = {"today": 0, "tomorrow": 1, "yesterday": -1}


def resolve_relative_date(query: str) -> str | None:
    q = query.lower()
    for word, offset in RELATIVE_DATE_OFFSETS.items():
        if re.search(rf"\b{word}\b", q):
            return (datetime.now().date() + timedelta(days=offset)).strftime("%Y-%m-%d")
    return None


def build_date_patterns(month_names: list[str]) -> list[re.Pattern]:
    """Numbers are where dense embeddings fall apart -- "2nd of Edavam" and "5th of
    Edavam" look almost identical to the model -- so any phrasing that pins down a
    specific Malayalam date is resolved here, exactly. The month names come from
    whatever data is actually loaded, not a fixed list, so adding a new month's JSON
    is enough to make its name recognized -- no regex edits required."""
    month_alt = "|".join(re.escape(m) for m in month_names)
    patterns = []
    if month_alt:
        patterns.append(re.compile(rf"\b(?:malayalam date|{month_alt})\s*(\d{{1,2}})\b", re.IGNORECASE))
        patterns.append(re.compile(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+of\s+(?:this\s+)?(?:{month_alt}|malayalam)\b", re.IGNORECASE
        ))
    else:
        patterns.append(re.compile(r"\b(?:malayalam date)\s*(\d{1,2})\b", re.IGNORECASE))
    patterns.append(re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE))
    return patterns


def extract_malayalam_date(q: str, date_patterns: list[re.Pattern]) -> int | None:
    """Tries each date pattern from most to least specific, returns the first hit."""
    for pattern in date_patterns:
        m = pattern.search(q)
        if m:
            return int(m.group(1))
    return None


def mentioned_month(q: str, month_names: list[str]) -> str | None:
    for name in month_names:
        if name in q:
            return name
    return None


def try_direct_lookup(
    query: str, docs: list[dict], date_patterns: list[re.Pattern], month_names: list[str]
) -> tuple[list[dict], list[str] | None, str | None]:
    """Returns (matches, ambiguous_months, resolved_date). ambiguous_months is only
    non-None when a bare date/weekday (no month named in the query) matches days in
    more than one loaded month -- e.g. "5th" or "guruvaram" once multiple months are
    loaded -- in which case matches is empty and the caller should ask which month was
    meant instead of guessing or dumping every candidate into the LLM's context.
    resolved_date is the ISO date the query pinned down (literal or "today"/"tomorrow"/
    "yesterday"), even if matches ended up empty -- lets the caller tell a user "that
    date isn't in the loaded data" instead of silently falling through to fuzzy search,
    which can't answer a specific-date question anyway."""
    q = query.lower()

    relative_date = resolve_relative_date(query)
    if relative_date:
        return [d for d in docs if d["gregorian_date"] == relative_date], None, relative_date

    m = GREGORIAN_DATE_RE.search(query)
    if m:
        gdate = m.group(0)
        return [d for d in docs if d["gregorian_date"] == gdate], None, gdate

    named_month = mentioned_month(q, month_names)

    def resolve(candidates: list[dict]) -> tuple[list[dict], list[str] | None, str | None]:
        if named_month:
            return [d for d in candidates if (d["malayalam_month"] or "").lower() == named_month], None, None
        months_present = sorted({d["malayalam_month"] for d in candidates if d["malayalam_month"]})
        if len(months_present) > 1:
            return [], months_present, None
        return candidates, None, None

    mdate = extract_malayalam_date(q, date_patterns)
    if mdate is not None:
        return resolve([d for d in docs if d["malayalam_date"] == mdate])

    for wd in WEEKDAYS:
        if wd in q:
            return resolve([d for d in docs if d["weekday"] and d["weekday"].lower() == wd])

    return [], None, None


# ---------------- Keyword / fuzzy search layer ----------------
# Handles the other thing embeddings are bad at: unfamiliar proper nouns (temple and
# festival names) and typos in them ("pradhoksham" for "Pradosham", "bagavathy" for
# "Bhagavad"). This is a cheap exact-substring + fuzzy pass over each day's raw text,
# run alongside embedding search rather than instead of it.
BASE_STOPWORDS = {
    "when", "what", "which", "where", "does", "day", "date", "time", "this", "that",
    "the", "for", "special", "event", "function", "programme", "program", "happening",
    "malayalam", "month", "temple", "calendar", "panchang", "about", "tell",
    # query-intent words for the "next occurrence" layer -- not content to match on
    "next", "upcoming", "coming",
    # honorifics/ritual words that recur across many unrelated temple entries and would
    # otherwise make almost every day "match" a temple-name query
    "sree", "prathishtha", "dinam", "kshetra", "kshetram",
}
# Month names (Edavam, Chingam, ...) are merged in at startup from whatever data is
# actually loaded -- see build_stopwords() -- instead of being hardcoded here.


def build_stopwords(month_names: list[str]) -> set[str]:
    return BASE_STOPWORDS | set(month_names)


def keyword_search(query: str, docs: list[dict], stopwords: set[str], min_ratio: float = 0.75) -> list[dict]:
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", query.lower()) if w not in stopwords]
    if not words:
        return []

    matches = []
    for d in docs:
        doc_text_lower = d["text"].lower()
        doc_words = re.findall(r"[a-zA-Z]{4,}", doc_text_lower)
        for w in words:
            if w in doc_text_lower or difflib.get_close_matches(w, doc_words, n=1, cutoff=min_ratio):
                matches.append(d)
                break
    return matches


def find_next_occurrence(query: str, docs: list[dict], stopwords: set[str]) -> list[dict] | None:
    """"When's the next Ekadashi/Pradosham" is the second most common real-world
    question, and a plain keyword_search answers it badly -- it returns every day that
    festival ever fell on across all loaded months, past and future alike, with no
    sense of "next". This only activates on next/upcoming/coming phrasing, then sorts
    keyword matches by date and prefers ones on or after today. Returns None (not an
    empty list) when the query isn't a "next X" question at all, so the caller knows to
    fall through to generic search rather than treating "no matches" as a real answer."""
    q = query.lower()
    if not any(w in q for w in ("next", "upcoming", "coming")):
        return None

    dated_matches = sorted(
        (d for d in keyword_search(query, docs, stopwords) if d["gregorian_date"]),
        key=lambda d: d["gregorian_date"],
    )
    if not dated_matches:
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    upcoming = [d for d in dated_matches if d["gregorian_date"] >= today]
    return (upcoming or dated_matches)[:3]


# ---------------- LLM generation ----------------
SYSTEM_PROMPT = """You are a helpful assistant answering questions about a Saraswat
Panchang (traditional Malayalam calendar), covering one or more months.

Rules:
- Answer ONLY using the CONTEXT provided below. Do not invent tithis, nakshatras,
  dates, or events that are not in the context.
- If the context doesn't contain enough information to answer confidently, say so
  plainly instead of guessing.
- Some facts come from a hand-scanned source. If the context says a value was "not
  confidently recorded" or marks something "(uncertain reading)", pass that
  uncertainty along to the user (e.g. "the source isn't fully clear on this, but...")
  instead of stating it as settled fact.
- Reply in natural, conversational language (mix of English/Malayalam terms is fine,
  matching how the user asked).
- Keep answers concise unless the user asks for detail.
"""


def generate_reply(query: str, context_docs: list[dict], note: str | None = None) -> str:
    context_text = "\n\n".join(d["text"] for d in context_docs) if context_docs else \
        "No matching data was found in this panchang for the question asked."
    if note:
        context_text = f"{note}\n\n{context_text}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{context_text}\n\nQUESTION: {query}"},
    ]

    last_error: Exception | None = None
    for model in LLM_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=900,
            )
        except Exception as exc:
            # Rate-limited (429), pulled from free (404), or otherwise unavailable --
            # try the next model in the chain rather than failing the whole request.
            logging.warning("LLM model %s failed, falling back: %s", model, exc)
            last_error = exc
            continue

        content = response.choices[0].message.content
        # The free-tier model occasionally returns empty content (hit during testing)
        # -- observed on a reasoning-style model that can spend its whole token budget
        # on hidden reasoning and leave nothing for the actual answer. Treat as a
        # failure of this model and fall through, rather than returning nothing.
        if content and content.strip():
            return content.strip()
        logging.warning("LLM model %s returned empty content, falling back", model)

    # Every model in the chain failed or returned nothing usable.
    if last_error is not None:
        raise last_error
    return ("Sorry, I couldn't put together a reply for that just now -- "
             "please try again or rephrase the question.")


# ---------------- Chat state + top-level query orchestration ----------------
class ChatState:
    """Everything needed to answer a query, built once (at CLI startup or API server
    startup) and reused across every question -- loading data and building/loading
    embeddings per-request would be needlessly slow and would rebuild the cache check
    on every call."""

    def __init__(self):
        self.datasets = load_all_data()
        self.month_names = collect_month_names(self.datasets)
        self.date_patterns = build_date_patterns(self.month_names)
        self.stopwords = build_stopwords(self.month_names)
        self.docs = build_documents(self.datasets)
        self.embedder = get_embedder()
        self.doc_vecs = build_or_load_embeddings(self.docs)

        loaded_dates = sorted(d["gregorian_date"] for d in self.docs if d["gregorian_date"])
        self.loaded_range = f"{loaded_dates[0]} to {loaded_dates[-1]}" if loaded_dates else "no dates loaded"
        self.loaded_months_label = ", ".join(m.title() for m in self.month_names) or "unknown month(s)"


def answer_query(state: ChatState, query: str) -> dict:
    """Runs the full layered pipeline (direct lookup -> next-occurrence -> keyword+
    embedding -> LLM) for one query and returns a structured result. Both the CLI and
    the API render this the same way conceptually, so the branching logic (ambiguous
    month? date outside loaded range? nothing found? normal answer?) lives here once
    instead of being duplicated per surface.

    Returns a dict with a "status" key:
    - "ambiguous"        -> {"ambiguous_months": [...]}
    - "date_not_covered" -> {"resolved_date": ..., "loaded_range": ..., "loaded_months": ...}
    - "not_found"        -> {}
    - "answered"         -> {"reply": ..., "match_source": ..., "matches": [...]}
    """
    matches, ambiguous_months, resolved_date = try_direct_lookup(
        query, state.docs, state.date_patterns, state.month_names
    )

    if ambiguous_months:
        return {"status": "ambiguous", "ambiguous_months": [m.title() for m in ambiguous_months]}

    if resolved_date and not matches:
        return {
            "status": "date_not_covered",
            "resolved_date": resolved_date,
            "loaded_range": state.loaded_range,
            "loaded_months": state.loaded_months_label,
        }

    match_source = "direct lookup"
    if not matches:
        next_matches = find_next_occurrence(query, state.docs, state.stopwords)
        if next_matches is not None:
            match_source = "next-occurrence"
            matches = next_matches

    if not matches and match_source != "next-occurrence":
        match_source = "keyword+similarity"
        kw_matches = keyword_search(query, state.docs, state.stopwords)

        q_vec = embed_query(query, state.embedder)
        top = cosine_top_k(q_vec, state.doc_vecs, TOP_K)
        sim_matches = [state.docs[i] for i, score in top if score >= SIM_THRESHOLD]

        seen = set()
        matches = []
        for d in kw_matches + sim_matches:
            key = (d["gregorian_date"], d.get("malayalam_month"))
            if key not in seen:
                seen.add(key)
                matches.append(d)

    if not matches:
        return {"status": "not_found"}

    # The LLM has no way to know what "today" is from the context text alone, so a
    # "next X" query would leave it guessing (or refusing) even though we've already
    # picked the right entries -- state today's date and what the ordering means
    # explicitly instead of letting it infer.
    note = None
    if match_source == "next-occurrence":
        today_str = datetime.now().strftime("%Y-%m-%d")
        has_upcoming = any(d["gregorian_date"] >= today_str for d in matches)
        note = f"Today's date is {today_str}. The entries below are sorted earliest first."
        if has_upcoming:
            note += " The first one on or after today is the next occurrence being asked about."
        else:
            note += (" None of them fall on or after today -- today is outside the loaded "
                      "panchang months, so these are simply the matching occurrences "
                      "available in the loaded data. Say so plainly rather than calling any of them 'next'.")

    reply = generate_reply(query, matches, note=note)
    return {"status": "answered", "reply": reply, "match_source": match_source, "matches": matches}
