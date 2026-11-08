"""Radar Okazji PRO: public catalog is refreshed by GitHub Actions.
Render reads the latest published JSON independently of code deployments.
"""
import json
import time
import threading
import html
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests
from flask import Flask, jsonify, Response

BASE = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE / "static"))
DATA_URL = "https://raw.githubusercontent.com/marchewka1988marcin-jpg/radar-okazji-pro/main/data/verified.json"
cache = {"value": None, "checked": 0, "last_error": None, "source": "unknown"}
lock = threading.Lock()

def read_offers():
    with lock:
        if cache["value"] is not None and time.monotonic() - cache["checked"] < 30:
            return cache["value"]
        try:
            r = requests.get(DATA_URL, params={"cache": int(time.time() // 60)}, timeout=(3, 8),
                              headers={"User-Agent": "RadarOkazji/2.0"})
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
                raise ValueError("Invalid JSON catalog")
            cache.update({"value": data, "checked": time.monotonic(),
                          "last_error": None, "source": "github_raw"})
            return data
        except Exception as exc:
            cache["last_error"] = str(exc)[:240]
            cache["checked"] = time.monotonic()
            app.logger.warning("Fresh catalog temporarily unavailable: %s", exc)
            if cache["value"] is not None:
                cache["source"] = "stale_memory"
                return dict(cache["value"], warning="Nie można pobrać najnowszego katalogu; ostatnia zapisana kopia.")
            try:
                data = json.loads((BASE / "data/verified.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {"offers": [], "updated_at": None, "status": "Dane chwilowo niedostępne"}
            cache.update({"value": data, "source": "local_backup"})
            return dict(data, warning="Wyświetlana jest kopia awaryjna, nie najnowszy katalog.")

def safe_url(value):
    try:
        p = urlsplit(str(value or ""))
        return p.scheme == "https" and bool(p.hostname)
    except ValueError:
        return False

@app.get("/")
def index():
    """Server-side fallback cards remain readable without JavaScript."""
    data = read_offers()
    template = (BASE / "static/index.html").read_text(encoding="utf-8")
    cards = []
    for o in data.get("offers", [])[:250]:
        url = str(o.get("url") or "")
        if not safe_url(url):
            continue
        title = html.escape(str(o.get("title") or "Ogłoszenie"))
        description = html.escape(str(o.get("description") or ""))
        source = html.escape(str(o.get("query") or ""))
        link = html.escape(url, quote=True)
        cards.append('<article class="card offer"><h3>' + title +
                     '</h3><p class="muted">' + description +
                     '</p><div class="small muted">' + source +
                     '</div><a href="' + link +
                     '" target="_blank" rel="noopener noreferrer">Otwórz ofertę ↗</a></article>')
    template = template.replace('<section id="results" aria-live="polite"></section>',
                                '<section id="results" aria-live="polite">' + "".join(cards) + '</section>')
    template = template.replace('id="count">0 wyników',
                                'id="count">' + str(len(cards)) + ' wyników')
    template = template.replace('Odczytuję aktualizację…',
                                'Dane: ' + html.escape(str(data.get("updated_at") or "brak daty")))
    return Response(template, mimetype="text/html",
                    headers={"Cache-Control": "no-store, max-age=0"})

@app.get("/health")
def health():
    data = read_offers()
    ts = data.get("updated_at")
    try:
        age_hours = (datetime.now(timezone.utc) -
                     datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600
    except (ValueError, TypeError, AttributeError):
        age_hours = None
    fresh = age_hours is not None and -1 <= age_hours < 9
    source_ok = cache["source"] == "github_raw" and not cache["last_error"]
    response = jsonify({
        "ok": fresh and source_ok,
        "fresh": fresh,
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "updated_at": ts,
        "count": len(data.get("offers", [])),
        "source": cache["source"],
        "error": cache["last_error"],
        "source_health": data.get("source_health", {})
    })
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

@app.get("/api/offers")
def offers():
    data = read_offers()
    response = jsonify(data)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response
