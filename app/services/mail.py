# app/services/mail.py
import smtplib, ssl
from email.message import EmailMessage
from typing import Optional
from app.config import get_settings

def _build_client():
    s = get_settings()
    if s.SMTP_USE_SSL:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, context=context)
    else:
        server = smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
    if s.SMTP_USERNAME:
        server.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
    return server

def send_email(to: str, subject: str, html: str, text_fallback: Optional[str] = None) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject

    if not text_fallback:
        # fallback testuale minimo da HTML
        text_fallback = _html_to_text(html)

    msg.set_content(text_fallback)
    msg.add_alternative(html, subtype="html")

    with _build_client() as client:
        client.send_message(msg)

def _html_to_text(html: str) -> str:
    # super-semplice: rimuove i tag principali
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
