# app/routers/chat.py (versione aggiornata, compatibile con quanto già hai)
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, date

from app.services import kb
from app.services.sheets import find_booking, read_row_by_index
from app.services.ai import ask_llm

router = APIRouter(tags=["chat"])

class ChatReq(BaseModel):
    message: str
    propertyId: str = "CT-01"
    locale: str = "it"
    arrival_date: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None

class ChatRes(BaseModel):
    text: str
    used_ai: bool

def _load_guest_row(req: ChatReq) -> Dict[str,str]:
    if req.arrival_date and req.last_name:
        idx, rec, count = find_booking(req.arrival_date, req.last_name, req.first_name, req.propertyId)
        if count == 1 and idx:
            return read_row_by_index(idx)
    return {}

def _hello(name: str | None, locale: str) -> str:
    if not name: return ""
    return ("Ciao " if locale == "it" else "Hi ") + name + ", "

@router.post("/chat", response_model=ChatRes)
def chat(req: ChatReq):
    t = req.message.lower().strip()
    row = _load_guest_row(req)

    now = datetime.now()
    sez = kb.season(now.date())
    dayp = kb.daypart(now)

    # CONTEXT per placeholder rule-based
    ctx: Dict[str, Any] = {**row}
    ci = kb.get_checkin(req.propertyId, req.locale) or {}
    co = kb.get_checkout(req.propertyId, req.locale) or {}
    ctx.setdefault("checkin_start", ci.get("start", "12:00"))
    ctx.setdefault("checkin_end", ci.get("end", "22:00"))
    ctx.setdefault("checkout_time", co.get("time", "11:00"))
    hello = _hello(row.get("guest_first_name") or row.get("guest_last_name"), req.locale)

    # ---- RULE-BASED GRATIS (come già fatto) ----
    # ... (qui rimane tutto il blocco intenti che avevamo inserito: Wi-Fi, check-in/out, codice con gate, ecc.)
    # Se nessuna regola risponde, facciamo AI.

    # ---- AI COME “PARLATORE” (NO WEB) ----
    snippets = kb.kb_snippets_for(req.message, req.propertyId, req.locale, top_k=6)
    answer = ask_llm(
        req.message,
        context_snippets=snippets,
        booking_row=row,
        property_id=req.propertyId,
        locale=req.locale,
        season=sez,
        daypart=dayp,
    )
    return ChatRes(text=hello + answer, used_ai=True)

