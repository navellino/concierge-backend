from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
import re
from datetime import date, datetime, time

# percorso del file di conoscenza
KB_PATH = Path(__file__).resolve().parents[2] / "conoscenza.txt"

# -------------------------------------------------
# 1. FUNZIONE VECCHIA (wifi diretto) – la lascio
# -------------------------------------------------
def get_wifi(property_id: str, lang: str = "it") -> Optional[dict]:
    """
    Versione semplice: cerca nel file una sezione con 'WI-FI' e tag property/lang.
    La teniamo per retrocompatibilità.
    """
    try:
        text = KB_PATH.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return None

    blocks = text.split("#")
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        header = b.splitlines()[0:1]
        body = "\n".join(b.splitlines()[1:])
        if "WI-FI" in "".join(header).upper():
            if f"@property:{property_id}" in body and f"@lang:{lang}" in body:
                ssid = _pull(body, "SSID:")
                pwd = _pull(body, "PASSWORD:")
                note = _pull(body, "NOTE:")
                return {"ssid": ssid, "password": pwd, "note": note}
    return None


def _pull(block: str, key: str) -> Optional[str]:
    for line in block.splitlines():
        if line.strip().startswith(key):
            return line.split(":", 1)[1].strip()
    return None

# -------------------------------------------------
# 2. NUOVO PARSER A SEZIONI
# -------------------------------------------------

def _read_kb() -> str:
    try:
        return KB_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _parse_sections() -> list[dict]:
    """
    Legge conoscenza.txt e lo trasforma in una lista di sezioni strutturate.
    Formato atteso:
    # WIFI
    @property:CT-01 @lang:it
    SSID: ...
    PASSWORD: ...
    """
    raw = _read_kb()
    if not raw:
        return []

    blocks = re.split(r"(?m)^\s*#\s*", raw)
    out: list[dict] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        lines = b.splitlines()
        name = lines[0].strip().upper()
        rest = "\n".join(lines[1:]).strip()

        # tag
        mprop = re.search(r"@property:([A-Za-z0-9\-_\.]+)", rest)
        prop = mprop.group(1) if mprop else None

        mlang = re.search(r"@lang:([a-z]{2})", rest, re.I)
        lang = mlang.group(1).lower() if mlang else "it"

        kv: Dict[str, str] = {}
        text_lines = []
        items = []

        for line in rest.splitlines():
            line = line.rstrip()
            if line.startswith("@"):
                continue
            if re.match(r"^[A-Z_]+:", line):
                k, v = line.split(":", 1)
                kv[k.strip().upper()] = v.strip()
            elif line.startswith("-"):
                items.append(line[1:].strip())
            else:
                text_lines.append(line)

        out.append({
            "name": name,
            "property": prop,
            "lang": lang,
            "kv": kv,
            "text": "\n".join(text_lines).strip(),
            "items": items
        })

    return out

# 👇👇 QUI mancava la riga che ti dava errore
_SECTIONS = _parse_sections()

def _clean_kb_value(value: str) -> str:
    if not value:
        return ""
    cleaned = value.replace("\\\\n", "\n")
    cleaned = re.sub(r"\\+\s*\n", "\n", cleaned)
    cleaned = cleaned.replace("\\\\", "")
    cleaned = cleaned.replace("\\", "")
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n".join(lines).strip()
# -------------------------------------------------
# 3. HELPER PER TROVARE SEZIONI
# -------------------------------------------------
def _find_section(name: str, property_id: str, lang: str = "it") -> Optional[dict]:
    name = name.upper()
    # prima: match perfetto
    for s in _SECTIONS:
        if s["name"] == name and s["property"] == property_id and s["lang"] == lang:
            return s
    # fallback: solo property
    for s in _SECTIONS:
        if s["name"] == name and s["property"] == property_id:
            return s
    # fallback: solo nome
    for s in _SECTIONS:
        if s["name"] == name:
            return s
    return None

# -------------------------------------------------
# 4. API SPECIFICHE (checkin, checkout, ecc.)
# -------------------------------------------------
def get_checkin(property_id: str, lang: str = "it") -> Optional[dict]:
    s = _find_section("CHECKIN", property_id, lang)
    if not s:
        return None
    return {
        "start": s["kv"].get("START", "12:00"),
        "end": s["kv"].get("END", "22:00"),
        "text": s["kv"].get("TEXT") or s["text"]
    }

def get_checkout(property_id: str, lang: str = "it") -> Optional[dict]:
    s = _find_section("CHECKOUT", property_id, lang)
    if not s:
        return None
    return {
        "time": s["kv"].get("TIME", "10:00"),
        "text": s["kv"].get("TEXT") or s["text"]
    }

def get_emergency(property_id: str, lang: str = "it") -> Optional[dict]:
    s = _find_section("EMERGENCY", property_id, lang)
    if not s:
        return None
    return {
        "host_phone": s["kv"].get("HOST_PHONE"),
        "text": s["kv"].get("TEXT") or s["text"]
    }

def get_parking(property_id: str, lang: str = "it") -> Optional[str]:
    s = _find_section("PARKING", property_id, lang)
    if not s:
        return None
    return s["kv"].get("TEXT") or s["text"]

def get_initial_info(property_id: str, lang: str = "it") -> Optional[dict]:
    section = _find_section("INFO_INIZIALI", property_id, lang)
    if not section:
        return None

    parts: list[str] = []

    primary_text = _clean_kb_value(section["kv"].get("TEXT", ""))
    if primary_text:
        parts.append(primary_text)

    extra_text = _clean_kb_value(section.get("text", ""))
    if extra_text:
        parts.append(extra_text)

    for key, value in section["kv"].items():
        if key == "TEXT":
            continue
        cleaned = _clean_kb_value(value)
        if cleaned:
            parts.append(cleaned)

    for item in section.get("items", []):
        cleaned = _clean_kb_value(item)
        if cleaned:
            parts.append(cleaned)

    combined_text = "\n".join(part for part in parts if part).strip()

    time_candidates: list[str] = []
    for source in (primary_text, extra_text, combined_text):
        if not source:
            continue
        for match in re.findall(r"\b(\d{1,2}:\d{2})\b", source):
            if match not in time_candidates:
                time_candidates.append(match)

    checkin_time = time_candidates[0] if time_candidates else None
    checkout_time = time_candidates[1] if len(time_candidates) > 1 else None

    return {
        "text": combined_text,
        "checkin_time": checkin_time,
        "checkout_time": checkout_time,
    }

def get_restaurants(property_id: str, lang: str = "it") -> Optional[list[str]]:
    s = _find_section("RESTAURANTS", property_id, lang)
    if not s:
        return None
    return s["items"]

def get_sea(property_id: str, lang: str = "it", today: date | None = None) -> Optional[str]:
    s = _find_section("SEA", property_id, lang)
    if not s:
        return None
    today = today or date.today()
    is_winter = today.month in (11,12,1,2)
    key = "WINTER" if is_winter else "SUMMER"
    return s["kv"].get(key) or s["text"]

# -------------------------------------------------
# 5. CONTESTO STAGIONALE / ORARIO
# -------------------------------------------------
def season_context(today: date) -> dict:
    m = today.month
    is_winter = m in (11,12,1,2)
    is_summer = m in (6,7,8)
    return {"is_winter": is_winter, "is_summer": is_summer}

def season(today: date) -> str:
    m = today.month
    if m in (12, 1, 2): return "winter"
    if m in (3, 4, 5):  return "spring"
    if m in (6, 7, 8):  return "summer"
    return "autumn"

def daypart(now: datetime) -> str:
    h = now.hour
    if 5 <= h < 12:  return "morning"
    if 12 <= h < 18: return "afternoon"
    if 18 <= h < 23: return "evening"
    return "night"

# -------------------------------------------------
# 6. GATE PER CODICE PORTA
# -------------------------------------------------
def time_gate_for_code(now: datetime, row: Dict[str,str]) -> Optional[str]:
    if (row.get("authorized","no").lower() != "yes"):
        return "Il self check-in non è ancora autorizzato dall'host."
    hhmm = (row.get("checkin_time") or "12:00")
    try:
        h, m = map(int, hhmm.split(":"))
        release = datetime.combine(now.date(), time(h, m))
        if now < release:
            return f"Posso condividere il codice dalle {hhmm} del giorno di arrivo."
    except Exception:
        pass
    return None

# -------------------------------------------------
# 7. SNIPPET PER L’AI
# -------------------------------------------------
def kb_snippets_for(query: str, property_id: str, lang: str, top_k: int = 6) -> list[str]:
    q = query.lower()
    candidates: list[tuple[float, str]] = []
    for s in _SECTIONS:
        if s["property"] not in (None, property_id):
            continue
        if s["lang"] not in (lang,):
            continue
        body = "\n".join([
            s["name"],
            "\n".join(f"{k}: {v}" for k, v in s["kv"].items()),
            s["text"],
            "\n".join(s["items"]),
        ]).strip()
        if not body:
            continue
        score = 0.0
        for token in set(re.findall(r"[a-zà-ù0-9]+", q)):
            if token and token in body.lower():
                score += 1.0
        score -= 0.05 * len(s["items"])
        if score > 0:
            candidates.append((score, body))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [body for _, body in candidates[:top_k]]

# -------------------------------------------------
# 8. RENDER PLACEHOLDER
# -------------------------------------------------
def render(text: str, ctx: Dict[str, Any]) -> str:
    def repl(m):
        key = m.group(1)
        return str(ctx.get(key, m.group(0)))
    return re.sub(r"\{([A-Za-z0-9_\.]+)\}", repl, text)
