# app/config.py
import os, json

class Settings:
    def __init__(self):
        # variabili generali
        self.JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
        self.GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

        # service account JSON su UNA riga nel .env
        sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
        try:
            self.GOOGLE_SERVICE_ACCOUNT_JSON = json.loads(sa)
        except Exception:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON non è un JSON valido. Controlla il .env.")

        # --- SMTP ---
        self.SMTP_HOST = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        # mittente: usa quello passato o, se vuoto, il nome utente SMTP
        self.SMTP_FROM = os.getenv("SMTP_FROM", self.SMTP_USERNAME or "no-reply@example.com")
        # true -> SSL (465); false -> STARTTLS (587)
        self.SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes", "y")

def get_settings() -> Settings:
    return Settings()
