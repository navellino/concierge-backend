# app/services/ai.py
import os
from typing import Dict, Any, List
from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
TEMP  = float(os.getenv("AI_TEMPERATURE", "0.2"))
MAXTK = int(os.getenv("AI_MAX_TOKENS", "350"))

SYSTEM_TEMPLATE = """You are a vacation-rental concierge for property {property_id}.
Rules (do not violate):
- Reply in the guest language: {locale}.
- Use ONLY the provided context and booking row. Do NOT browse the web or invent facts.
- Adapt suggestions to the current season: {season}, and daypart: {daypart}.
- If the user asks for door code:
  - Only provide it if booking.authorized == "yes" AND current time >= booking.checkin_time of the arrival day.
  - Otherwise, explain the rule and do not reveal the code.
- Be concise, practical, friendly, and specific. Use names if present.
- If an answer is not in context, say you will ask the host and offer alternatives.
"""

def ask_llm(user_msg: str, *, 
            context_snippets: List[str], 
            booking_row: Dict[str, Any], 
            property_id: str, locale: str, 
            season: str, daypart: str) -> str:
    system = SYSTEM_TEMPLATE.format(
        property_id=property_id, locale=locale, season=season, daypart=daypart
    )

    ctx_block = "### KNOWLEDGE\n" + "\n\n---\n".join(context_snippets) if context_snippets else "### KNOWLEDGE\n(none)"
    row_block = "### BOOKING_ROW\n" + (repr(booking_row) if booking_row else "{}")

    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{ctx_block}\n\n{row_block}\n\n### QUESTION ({locale})\n{user_msg}"}
    ]
    res = _client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=TEMP,
        max_tokens=MAXTK,
    )
    return res.choices[0].message.content.strip()
