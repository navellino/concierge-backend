import os
from typing import Dict, Any, List, Optional
from openai import OpenAI

# Leggo la chiave dalle variabili d'ambiente
API_KEY = os.getenv("OPENAI_API_KEY")

# inizialmente nessun client
_client: Optional[OpenAI] = None

# creo il client SOLO se ho la chiave
if API_KEY:
    _client = OpenAI(api_key=API_KEY)
# altrimenti lascio _client = None e poi userò un fallback

# valori di default per il modello
MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
TEMP  = float(os.getenv("AI_TEMPERATURE", "0.2"))
MAXTK = int(os.getenv("AI_MAX_TOKENS", "350"))

SYSTEM_TEMPLATE = """You are a vacation-rental concierge for property {property_id}.
Source knowledge is written in Italian.
The guest is writing in: {locale}. You MUST answer in {locale}.
You must NOT invent information that is not in the provided knowledge or booking row.
You may translate or rephrase the Italian knowledge into the guest language, keeping numbers, codes, times, phone numbers exactly the same.
Adapt suggestions to the current season: {season}, and daypart: {daypart}.
If the user asks for door code:
  - Only provide it if booking.authorized == "yes" AND current time >= booking.checkin_time of the arrival day.
  - Otherwise, explain the rule and do not reveal the code.
Be concise, practical, friendly, and specific.
"""

def ask_llm(
    user_msg: str,
    *,
    context_snippets: List[str],
    booking_row: Dict[str, Any],
    property_id: str,
    locale: str,
    season: str,
    daypart: str,
) -> str:
    """
    Funzione unica per parlare col modello.
    Se non c'è il client (_client is None) restituisce un messaggio di fallback
    così l'app non crasha e tu puoi testare il widget.
    """
    # se non abbiamo client (niente chiave o niente credito) → fallback
    if _client is None:
        return (
            "Il concierge è attivo ma il servizio AI non è configurato. "
            "Le risposte verranno gestite dall’host."
        )

    system = SYSTEM_TEMPLATE.format(
        property_id=property_id,
        locale=locale,
        season=season,
        daypart=daypart,
    )

    ctx_block = (
        "### KNOWLEDGE\n" + "\n\n---\n".join(context_snippets)
        if context_snippets
        else "### KNOWLEDGE\n(none)"
    )
    row_block = "### BOOKING_ROW\n" + (repr(booking_row) if booking_row else "{}")

    msgs = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"{ctx_block}\n\n{row_block}\n\n### QUESTION ({locale})\n{user_msg}",
        },
    ]

    resp = _client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=TEMP,
        max_tokens=MAXTK,
    )
    return resp.choices[0].message.content.strip()
