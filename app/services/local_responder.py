# app/services/local_responder.py

from typing import List

def answer_from_snippets(user_msg: str, snippets: List[str]) -> str | None:
    """
    Prova a dare una risposta senza AI usando gli snippet già estratti
    dal knowledge base.
    Restituisce una stringa se trova qualcosa, altrimenti None.
    """
    msg = user_msg.lower()

    # caso wifi
    if "wifi" in msg or "wi-fi" in msg or "password" in msg:
        for sn in snippets:
            if "wifi" in sn.lower() or "wi-fi" in sn.lower():
                return sn.strip()

    # qui puoi aggiungere altre chiavi fisse:
    # check-in, parcheggio, raccolta differenziata, ecc.

    return None
