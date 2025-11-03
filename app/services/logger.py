# app/services/logger.py
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.sheets import append_row  # usa la funzione che hai già per scrivere sullo Sheet

LOG_SHEET_NAME = "Logs"  # assicurati che questa tab esista nel tuo Google Sheet


def log_chat(
    *,
    property_id: str,
    locale: str,
    guest_msg: str,
    bot_msg: str,
    used_ai: bool,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Scrive una riga nel foglio Logs.
    Colonne suggerite:
    timestamp | property_id | locale | guest_msg | bot_msg | used_ai | extra
    """
    try:
        ts = datetime.now().isoformat(timespec="seconds")
        extra_str = ""
        if extra:
            extra_str = "; ".join(f"{k}={v}" for k, v in extra.items())

        row = [
            ts,
            property_id,
            locale,
            guest_msg,
            bot_msg,
            "yes" if used_ai else "no",
            extra_str,
        ]
        append_row(LOG_SHEET_NAME, row)

    except Exception as e:
        print(f"[LOGGER] Errore nel log_chat: {e}")
