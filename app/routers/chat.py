# app/routers/chat.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, date

from app.services.kb import kb_snippets_for, season, daypart
from app.services.local_responder import answer_from_snippets
from app.services.ai import ask_llm

router = APIRouter(tags=["chat"])


class ChatReq(BaseModel):
    message: str
    propertyId: str = "CT-01"
    locale: str = "it"
    arrival_date: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None


@router.post("/chat")
async def chat(payload: ChatReq) -> Dict[str, Any]:
    # 1. dati dalla richiesta
    user_msg = payload.message
    property_id = payload.propertyId or "CT-01"
    locale = payload.locale or "it"

    # 2. calcolo stagione e fascia oraria (le hai già in kb.py)
    today = date.today()
    now = datetime.now()
    current_season = season(today)
    current_daypart = daypart(now)

    # 3. prendo gli snippet dal knowledge base
    snippets = kb_snippets_for(
        query=user_msg,
        property_id=property_id,
        lang=locale,
        top_k=6,
    )

    # 4. prima provo SENZA AI (wifi, cose semplici)
    local_answer = answer_from_snippets(user_msg, snippets)
    if local_answer:
        if locale != "it":
            # chiedi all'AI solo di tradurre la risposta locale
            translated = ask_llm(
                f"Translate this into {locale}, keep all codes and numbers identical:\n{local_answer}",
                context_snippets=[],
                booking_row={},
                property_id=property_id,
                locale=locale,
                season=current_season,
                daypart=current_daypart,
            )
            return {"text": translated, "used_ai": True}
        return {"text": local_answer, "used_ai": False}

    # 5. se non ho trovato nulla nei testi, chiamo l’AI
    ai_answer = ask_llm(
        user_msg,
        context_snippets=snippets,
        booking_row={},          # qui dopo puoi mettere la riga di Google Sheets
        property_id=property_id,
        locale=locale,
        season=current_season,
        daypart=current_daypart,
    )

    return {
        "text": ai_answer,
        "used_ai": True,
    }
