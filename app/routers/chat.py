# app/routers/chat.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, date

from app.services.kb import kb_snippets_for, season, daypart
from app.services.local_responder import answer_from_snippets
from app.services.ai import ask_llm
from app.services import sheets
from app.services.logger import log_chat  # questo l'abbiamo creato prima

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
    user_msg = payload.message
    property_id = payload.propertyId or "CT-01"
    locale = payload.locale or "it"

    # stagione e fascia oraria
    today = date.today()
    now = datetime.now()
    current_season = season(today)
    current_daypart = daypart(now)

    # 1) PROVA A TROVARE LA PRENOTAZIONE DALLO SHEET
    booking_row: Dict[str, Any] = {}
    booking_row_index: Optional[int] = None

    if payload.arrival_date and payload.last_name:
        idx, rec, count = sheets.find_booking(
            arrival_date=payload.arrival_date,
            last_name=payload.last_name,
            first_name=payload.first_name,
            property_id=property_id,
        )
        if count == 1 and rec:
            booking_row = rec
            booking_row_index = idx  # lo teniamo, magari dopo lo usiamo

    # 2) PRENDI GLI SNIPPET DAL KNOWLEDGE BASE
    snippets = kb_snippets_for(
        query=user_msg,
        property_id=property_id,
        lang=locale,
        top_k=6,
    )

    # 3) PROVA PRIMA LA RISPOSTA LOCALE (wifi ecc.)
    local_answer = answer_from_snippets(user_msg, snippets)
    if local_answer:
        # se non è italiano facciamo tradurre solo quella risposta
        if locale != "it":
            translated = ask_llm(
                f"Translate this into {locale}, keep all codes and numbers identical:\n{local_answer}",
                context_snippets=[],
                booking_row=booking_row,
                property_id=property_id,
                locale=locale,
                season=current_season,
                daypart=current_daypart,
            )
            try:
                log_chat(
                    property_id=property_id,
                    locale=locale,
                    guest_msg=user_msg,
                    bot_msg=translated,
                    used_ai=True,
                    extra={"booking_found": bool(booking_row)},
                )
            except Exception:
                pass
            return {"text": translated, "used_ai": True}

        # italiano → rispondiamo diretti
        try:
            log_chat(
                property_id=property_id,
                locale=locale,
                guest_msg=user_msg,
                bot_msg=local_answer,
                used_ai=False,
                extra={"booking_found": bool(booking_row)},
            )
        except Exception:
            pass

        return {"text": local_answer, "used_ai": False}

    # 4) SE NON HO RISPOSTA LOCALE → CHIEDO ALL'AI
    ai_answer = ask_llm(
        user_msg,
        context_snippets=snippets,
        booking_row=booking_row,      # qui passa anche i dati della prenotazione
        property_id=property_id,
        locale=locale,
        season=current_season,
        daypart=current_daypart,
    )

    try:
        log_chat(
            property_id=property_id,
            locale=locale,
            guest_msg=user_msg,
            bot_msg=ai_answer,
            used_ai=True,
            extra={"booking_found": bool(booking_row)},
        )
    except Exception:
        pass

    return {
        "text": ai_answer,
        "used_ai": True,
    }
