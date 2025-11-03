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
    departure_date: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    guest_email: Optional[str] = None
    phone: Optional[str] = None
    first_access: bool = False


@router.post("/chat")
async def chat(payload: ChatReq) -> Dict[str, Any]:
    user_msg = payload.message
    property_id = payload.propertyId or "CT-01"
    locale = payload.locale or "it"

    def _log_and_return(text: str, used_ai: bool, extra: Optional[Dict[str, Any]] = None):
        try:
            log_chat(
                property_id=property_id,
                locale=locale,
                guest_msg=user_msg,
                bot_msg=text,
                used_ai=used_ai,
                extra=extra or {},
            )
        except Exception:
            pass
        return {"text": text, "used_ai": used_ai}

    # stagione e fascia oraria
    today = date.today()
    now = datetime.now()
    current_season = season(today)
    current_daypart = daypart(now)

# 0) FLUSSO REGISTRAZIONE RAPIDA PER PRENOTAZIONI SENZA DATI
    if payload.first_access:
        incomplete = sheets.list_incomplete_bookings(property_id=property_id)
        if incomplete:
            text = (
                "Ciao! Hai una prenotazione presso la nostra struttura? "
                "Se sì, indicami data di arrivo e di partenza (formato YYYY-MM-DD) "
                "così posso completare la registrazione al concierge."
            )
        else:
            text = (
                "Ciao! Al momento tutte le prenotazioni risultano già registrate. "
                "Se hai comunque bisogno di assistenza dimmi pure come posso aiutarti."
            )
        return _log_and_return(text, used_ai=False, extra={"flow": "first_access"})

    if payload.arrival_date and payload.departure_date and not payload.last_name:
        idx, rec, count = sheets.find_booking_by_dates(
            arrival_date=payload.arrival_date,
            departure_date=payload.departure_date,
            property_id=property_id,
            require_missing_details=False,
        )
        if count == 1 and rec:
            if (
                rec.get("guest_first_name")
                and rec.get("guest_last_name")
                and rec.get("guest_email")
            ):
                text = (
                    "Ho trovato la prenotazione per quelle date ma risulta già registrata. "
                    "Se hai bisogno di altro dimmelo pure."
                )
                return _log_and_return(text, used_ai=False, extra={"flow": "check_dates", "booking_found": True, "already_registered": True})
            text = (
                "Perfetto, ho trovato la tua prenotazione dal {arr} al {dep}. "
                "Per completare la registrazione ho bisogno di nome, cognome, numero di cellulare e indirizzo email."
            ).format(arr=rec.get("checkin_date", payload.arrival_date), dep=rec.get("checkout_date", payload.departure_date))
            return _log_and_return(text, used_ai=False, extra={"flow": "check_dates", "booking_found": True, "already_registered": False})
        if count == 0:
            text = (
                "Non trovo una prenotazione con data di arrivo {arr} e partenza {dep}. "
                "Puoi verificare le date o indicarmi altri dettagli?"
            ).format(arr=payload.arrival_date, dep=payload.departure_date)
            return _log_and_return(text, used_ai=False, extra={"flow": "check_dates", "booking_found": False})
        text = (
            "Ho trovato più prenotazioni con quelle date. "
            "Per favore forniscimi anche il nome e cognome per identificarti correttamente."
        )
        return _log_and_return(text, used_ai=False, extra={"flow": "check_dates", "booking_found": False, "ambiguous": True})

    if (
        payload.arrival_date
        and payload.departure_date
        and payload.first_name
        and payload.last_name
        and payload.guest_email
        and payload.phone
    ):
        idx, rec, count = sheets.find_booking_by_dates(
            arrival_date=payload.arrival_date,
            departure_date=payload.departure_date,
            property_id=property_id,
            require_missing_details=False,
        )
        if count == 1 and idx:
            if (
                rec
                and rec.get("guest_first_name")
                and rec.get("guest_last_name")
                and rec.get("guest_email")
                and not (rec.get("guest_email") == "" and payload.guest_email)
            ):
                text = (
                    "La prenotazione risulta già registrata. Se hai bisogno di altre informazioni chiedimi pure!"
                )
                return _log_and_return(text, used_ai=False, extra={"flow": "register", "booking_found": True, "already_registered": True})

            notes = rec.get("notes", "") if rec else ""
            if payload.phone:
                phone_note = f"Telefono ospite: {payload.phone}"
                if phone_note not in notes:
                    notes = (notes + "\n" if notes else "") + phone_note

            status_value = "pending"
            if rec and rec.get("status"):
                status_value = rec.get("status")

            update_payload = {
                "guest_first_name": payload.first_name,
                "guest_last_name": payload.last_name,
                "guest_email": payload.guest_email,
                "notes": notes,
                "locale": locale,
                "status": status_value or "pending",
                "guest_phone": payload.phone,
            }
            sheets.update_row_dict(idx, update_payload)
            text = (
                "Grazie {name}! Ho registrato la prenotazione: ora puoi utilizzare il concierge per qualsiasi domanda."
            ).format(name=payload.first_name)
            return _log_and_return(text, used_ai=False, extra={"flow": "register", "booking_found": True, "updated_row": idx})
        if count == 0:
            text = (
                "Non ho trovato una prenotazione con le date {arr} - {dep}. "
                "Controlla di averle inserite correttamente o contatta l'host."
            ).format(arr=payload.arrival_date, dep=payload.departure_date)
            return _log_and_return(text, used_ai=False, extra={"flow": "register", "booking_found": False})
        text = (
            "Ci sono più prenotazioni per quelle date. Potresti indicarmi il cognome usato nella prenotazione?"
        )
        return _log_and_return(text, used_ai=False, extra={"flow": "register", "booking_found": False, "ambiguous": True})

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
