from fastapi import FastAPI
from dotenv import load_dotenv
from app.routers import booking, chat, ical as ical_router, notify

def create_app() -> FastAPI:
    load_dotenv()  # legge .env se lo metteremo più avanti
    app = FastAPI(title="Concierge AI Agent", version="0.0.1")

    # aggancio delle rotte
    app.include_router(booking.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(ical_router.router, prefix="/api")
    app.include_router(notify.router, prefix="/api")

    @app.get("/")
    def root():
        return {"ok": True, "msg": "Concierge backend up"}

    return app

# questa variabile DEVE chiamarsi "app"
app = create_app()
