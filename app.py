"""G3Bot — OpenRouter proxy for vintage Macs (Netscape 4 / Mac OS 8.6).

A tiny Flask server that:
  1. Serves a Netscape-4-compatible HTML page over plain HTTP.
  2. Proxies chat requests to the OpenRouter HTTPS API.
  3. Caches the free-model list so the old browser never needs JS or TLS.
"""

import os
import time
import uuid
import threading

import requests as http_requests
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from markupsafe import Markup, escape

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CACHE_TTL = int(os.environ.get("G3BOT_CACHE_TTL", "3600"))
PORT = int(os.environ.get("G3BOT_PORT", "3615"))
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Tested working models (no credits required, confirmed 2026-04-28)
# Set G3BOT_ALLOWED_MODELS env var to override (comma-separated model IDs)
# ---------------------------------------------------------------------------
_DEFAULT_ALLOWED = {
    "inclusionai/ling-2.6-1t:free",
    "inclusionai/ling-2.6-flash:free",
    "baidu/qianfan-ocr-fast:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-3n-e2b-it:free",
    "google/gemma-3n-e4b-it:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
}
_env_allowed = os.environ.get("G3BOT_ALLOWED_MODELS", "")
ALLOWED_MODELS = (
    {m.strip() for m in _env_allowed.split(",") if m.strip()}
    if _env_allowed
    else _DEFAULT_ALLOWED
)

# ---------------------------------------------------------------------------
# Nice display names for known providers
# ---------------------------------------------------------------------------
COMPANY_DISPLAY = {
    "google": "Google",
    "meta-llama": "Meta",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral AI",
    "qwen": "Qwen",
    "microsoft": "Microsoft",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "nvidia": "NVIDIA",
    "cohere": "Cohere",
    "nousresearch": "Nous Research",
    "openchat": "OpenChat",
    "huggingfaceh4": "HuggingFace",
    "moonshotai": "Moonshot AI",
    "open-r1": "Open R1",
    "rekaai": "Reka AI",
    "allenai": "Allen AI",
    "openrouter": "OpenRouter",
    "agentica-org": "Agentica",
    "bytedance-research": "ByteDance",
    "thudm": "THUDM",
    "shisa-ai": "Shisa AI",
    "featherless-ai": "Featherless AI",
    "sophosympatheia": "Sophosympatheia",
    "cognitivecomputations": "Cognitive Computations",
    "mancer": "Mancer",
    "liquid": "Liquid AI",
    "thedrummer": "TheDrummer",
    "infermatic": "Infermatic",
}


def company_name(model_id: str) -> str:
    """Extract a human-friendly company name from a model id."""
    slug = model_id.split("/")[0] if "/" in model_id else model_id
    if slug in COMPANY_DISPLAY:
        return COMPANY_DISPLAY[slug]
    return " ".join(word.capitalize() for word in slug.split("-"))


def is_free(model: dict) -> bool:
    """Return True if the model is genuinely free on OpenRouter."""
    mid = model.get("id", "")
    if ":free" in mid:
        return True
    pricing = model.get("pricing")
    if not pricing:
        return False
    keys = ("prompt", "completion", "request", "image")
    saw_price = False
    for k in keys:
        val = pricing.get(k)
        if val is not None:
            saw_price = True
            try:
                if float(val) != 0.0:
                    return False
            except (ValueError, TypeError):
                return False
    return saw_price


def format_context(ctx: int | None) -> str:
    if not ctx:
        return "?"
    if ctx >= 1_000_000:
        return f"{ctx / 1_000_000:.1f}M"
    if ctx >= 1_000:
        return f"{ctx / 1_000:.0f}K"
    return str(ctx)


# ---------------------------------------------------------------------------
# Model cache (thread-safe)
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()
_cached_models: list[dict] = []
_cache_ts: float = 0.0


def _fetch_models() -> list[dict]:
    """Fetch free models from OpenRouter, return a sorted list of dicts."""
    if not OPENROUTER_API_KEY:
        return []
    try:
        resp = http_requests.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception:
        return []

    free_models = []
    for m in data:
        if not is_free(m):
            continue
        mid = m.get("id", "")
        if mid not in ALLOWED_MODELS:
            continue
        company = company_name(mid)
        ctx = m.get("context_length")
        free_models.append(
            {
                "id": mid,
                "company": company,
                "name": m.get("name", mid),
                "context": format_context(ctx),
                "context_raw": ctx or 0,
                "description": (m.get("description") or "")[:300],
            }
        )

    free_models.sort(key=lambda x: (x["company"].lower(), x["name"].lower()))
    return free_models


def get_models(force_refresh: bool = False) -> list[dict]:
    """Return cached models, refreshing if stale or forced."""
    global _cached_models, _cache_ts
    with _cache_lock:
        if force_refresh or (time.time() - _cache_ts > CACHE_TTL):
            _cached_models = _fetch_models()
            _cache_ts = time.time()
        return list(_cached_models)


# ---------------------------------------------------------------------------
# Pending requests store (for async chat processing)
# ---------------------------------------------------------------------------
_requests_lock = threading.Lock()
_pending_requests: dict = {}
_REQUEST_TTL = 600  # cleanup after 10 minutes
_conversation_history: list[dict] = []  # Protected by _requests_lock, max 50 messages


def _cleanup_old_requests():
    """Remove pending requests older than _REQUEST_TTL."""
    cutoff = time.time() - _REQUEST_TTL
    with _requests_lock:
        stale = [k for k, v in _pending_requests.items() if v["created_at"] < cutoff]
        for k in stale:
            del _pending_requests[k]


def _process_chat(req_id: str, model_id: str, prompt: str, history: list[dict]):
    """Background thread: call OpenRouter and store result."""
    result = {"response_text": "", "error_text": "", "status_text": ""}
    try:
        resp = http_requests.post(
            OPENROUTER_CHAT_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": history,
            },
            timeout=120,
        )
    except Exception as exc:
        result["error_text"] = f"Erreur reseau : {exc}"
        result["status_text"] = "Echec de la requete."
        with _requests_lock:
            # Remove user message added for this request if it remains the last entry
            if (_conversation_history
                and _conversation_history[-1].get("role") == "user"
                and _conversation_history[-1].get("content") == prompt):
                _conversation_history.pop()
            _pending_requests[req_id]["result"] = result
            _pending_requests[req_id]["status"] = "done"
        return

    if resp.status_code < 200 or resp.status_code >= 300:
        result["error_text"] = f"Erreur HTTP {resp.status_code} : {resp.text[:500]}"
        result["status_text"] = f"Erreur HTTP {resp.status_code}."
        with _requests_lock:
            # Remove user message added for this request if it remains the last entry
            if (_conversation_history
                and _conversation_history[-1].get("role") == "user"
                and _conversation_history[-1].get("content") == prompt):
                _conversation_history.pop()
            _pending_requests[req_id]["result"] = result
            _pending_requests[req_id]["status"] = "done"
        return

    # Parse response
    try:
        body = resp.json()
        choices = body.get("choices", [])
        text_parts = []
        for ch in choices:
            msg = ch.get("message", {})
            text_parts.append(msg.get("content", "") or ch.get("text", ""))
        response_text = "\n\n".join(text_parts) or resp.text[:2000]
    except Exception:
        response_text = resp.text[:2000]

    # Find model display name
    models = get_models()
    model_display = model_id
    for m in models:
        if m["id"] == model_id:
            model_display = f'{m["company"]} -- {m["name"]}'
            break

    result["response_text"] = response_text
    result["status_text"] = f"Reponse recue de {model_display}."

    with _requests_lock:
        _pending_requests[req_id]["result"] = result
        _pending_requests[req_id]["status"] = "done"


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico", mimetype="image/x-icon")


@app.template_filter("nl2br")
def nl2br_filter(value):
    """Convert newlines to <br> tags. Insert <wbr> in long words to prevent
    horizontal scrolling in old browsers without word-wrap support."""
    escaped = escape(value)
    words = str(escaped).split(" ")
    broken = []
    for word in words:
        if len(word) > 70:
            chunks = [word[i : i + 70] for i in range(0, len(word), 70)]
            broken.append("<wbr>".join(chunks))
        else:
            broken.append(word)
    text = " ".join(broken)
    text = text.replace("\n", Markup("<br>\n"))
    return Markup(text)


@app.route("/", methods=["GET"])
def index():
    models = get_models()
    with _requests_lock:
        history = list(_conversation_history)
    return render_template(
        "index.html",
        models=models,
        selected_model="openrouter/free",
        prompt_text="Parle-moi de l'iMac G3.",
        response_text="",
        error_text="",
        status_text=(
            f"{len(models)} modele(s) gratuit(s) disponible(s)."
            if models
            else "Aucun modele charge (verifiez la cle API)."
        ),
        history=history,
    )


@app.route("/clear")
def clear():
    with _requests_lock:
        _conversation_history.clear()
    models = get_models()
    with _requests_lock:
        history = list(_conversation_history)
    return render_template(
        "index.html",
        models=models,
        selected_model="",
        prompt_text="",
        response_text="",
        error_text="",
        status_text="",
        history=history,
    )


@app.route("/chat", methods=["POST"])
def chat():
    model_id = request.form.get("model", "")
    prompt = request.form.get("prompt", "")
    models = get_models()

    if not OPENROUTER_API_KEY:
        return render_template(
            "index.html",
            models=models,
            selected_model=model_id,
            prompt_text=prompt,
            response_text="",
            error_text="Cle API OpenRouter non configuree sur le serveur.",
            status_text="Erreur de configuration.",
            history=[],
        )

    if not model_id:
        return render_template(
            "index.html",
            models=models,
            selected_model=model_id,
            prompt_text=prompt,
            response_text="",
            error_text="Veuillez choisir un modele.",
            status_text="",
            history=[],
        )

    # Start background processing
    req_id = uuid.uuid4().hex[:8]
    with _requests_lock:
        # Add user message to conversation history
        _conversation_history.append({"role": "user", "content": prompt})
        # Enforce 50 message limit
        while len(_conversation_history) > 50:
            del _conversation_history[0]
        # Copy current history to pass to background thread (includes new user message)
        current_history = list(_conversation_history)
        # Create pending request entry
        _pending_requests[req_id] = {
            "status": "pending",
            "result": None,
            "progress": 5,
            "model": model_id,
            "prompt": prompt,
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_process_chat, args=(req_id, model_id, prompt, current_history), daemon=True
    )
    thread.start()

    _cleanup_old_requests()
    return redirect(url_for("wait", req_id=req_id))


@app.route("/wait/<req_id>")
def wait(req_id):
    with _requests_lock:
        entry = _pending_requests.get(req_id)
        if not entry:
            return redirect(url_for("index"))

        if entry["status"] == "pending":
            entry["progress"] = min(entry["progress"] + 8, 92)
            progress = entry["progress"]
            model_id = entry["model"]
            return render_template(
                "wait.html", progress=progress, req_id=req_id, model_id=model_id
            )

        # Done — extract result and clean up
        result = entry["result"]
        model_id = entry["model"]
        prompt = entry["prompt"]
        del _pending_requests[req_id]

    # Add assistant message to history if response was successful
    if result.get("response_text"):
        with _requests_lock:
            _conversation_history.append({"role": "assistant", "content": result["response_text"]})
            # Enforce 50 message limit
            while len(_conversation_history) > 50:
                del _conversation_history[0]

    models = get_models()
    with _requests_lock:
        history = list(_conversation_history)
    return render_template(
        "index.html",
        models=models,
        selected_model=model_id,
        prompt_text="",
        response_text=result.get("response_text", ""),
        error_text=result.get("error_text", ""),
        status_text=result.get("status_text", ""),
        history=history,
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    get_models(force_refresh=True)
    return redirect(url_for("index"))


@app.route("/models")
def models_page():
    models = get_models()
    return render_template("models.html", models=models)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    get_models(force_refresh=True)
    app.run(host="0.0.0.0", port=PORT, debug=False)
