# app/services/ai_limits.py
from typing import Optional, Dict, Any

from app.services import sheets

MAX_AI_CALLS = 8   # il tetto che avevi in mente


def get_booking_for_chat(
    property_id: str,
    arrival_date: str | None,
    last_name: str | None,
    first_name: str | None = None,
) -> tuple[Optional[int], Dict[str, Any]]:
    """
    Prova a trovare la prenotazione partendo dai dati che arrivano dal widget.
    Restituisce (row_index, row_dict).
    Se non trova nulla, restituisce (None, {}).
    """
    if not arrival_date or not last_name:
        return None, {}

    idx, rec, count = sheets.find_booking(
        arrival_date=arrival_date,
        last_name=last_name,
        first_name=first_name,
        property_id=property_id,
    )

    if count == 1 and rec:
        return idx, rec
    return None, {}


def can_use_ai(booking_row: Dict[str, Any]) -> bool:
    """
    Ritorna True se la prenotazione non ha ancora esaurito le chiamate AI.
    """
    calls = booking_row.get("ai_calls", "") or "0"
    try:
        calls_int = int(calls)
    except ValueError:
        calls_int = 0
    return calls_int < MAX_AI_CALLS


def increment_ai_calls(row_index: int, booking_row: Dict[str, Any]) -> None:
    """
    Incrementa il contatore ai_calls sulla riga della prenotazione.
    """
    calls = booking_row.get("ai_calls", "") or "0"
    try:
        calls_int = int(calls)
    except ValueError:
        calls_int = 0

    sheets.update_row_dict(row_index, {"ai_calls": calls_int + 1})
