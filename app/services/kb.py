from pathlib import Path
from typing import Optional
import re, datetime as dt
from pathlib import Path

KB_PATH = Path(__file__).resolve().parents[2] / "conoscenza.txt"

def get_wifi(property_id: str, lang: str = "it") -> Optional[dict]:
    text = KB_PATH.read_text(encoding="utf-8", errors="ignore")
    blocks = text.split("#")
    for b in blocks:
        header = b.strip().splitlines()[0:1]
        body = "\n".join(b.strip().splitlines()[1:])
        if "WI-FI" in "".join(header).upper():
            if f"@property:{property_id}" in body and f"@lang:{lang}" in body:
                ssid = _pull(body, "SSID:")
                pwd = _pull(body, "PASSWORD:")
                note = _pull(body, "NOTE:")
                return {"ssid": ssid, "password": pwd, "note": note}
    return None

def _pull(block: str, key: str) -> str | None:
    for line in block.splitlines():
        if line.strip().startswith(key):
            return line.split(":", 1)[1].strip()
    return None

# carica testo base (knowledge.txt) una sola volta
_KB = (Path("conoscenza.txt").read_text(encoding="utf-8") 
       if Path("conoscenza.txt").exists() else "")

def season_context(today: dt.date) -> dict:
    m = today.month
    is_winter = m in (11,12,1,2)
    is_summer = m in (6,7,8)
    return {"is_winter": is_winter, "is_summer": is_summer}

def rule_answer(q: str, ctx: dict) -> str | None:
    t = q.lower()
    # esempi semplici (espandi a piacere)
    if any(k in t for k in ("wifi", "wi-fi", "password")):
        return f"La password del Wi-Fi è: {ctx.get('wifi_coupon','—')}."
    if "check-in" in t or "checkin" in t:
        return f"Il check-in è dalle {ctx.get('checkin_time','12:00')}."
    if "check-out" in t or "checkout" in t:
        return f"Il check-out è entro le {ctx.get('checkout_time','10:00')}."
    if ("mare" in t or "spiaggia" in t) and ctx.get("is_winter"):
        return "Siamo in bassa stagione: molti lidi sono chiusi. Posso suggerire passeggiata sul lungomare e locali interni."
    # se vuoi, pesco da knowledge.txt con keyword “povere”
    if _KB:
        for line in _KB.splitlines():
            k, _, v = line.partition("|")
            if k and v and k.strip().lower() in t:
                return v.strip()
    return None