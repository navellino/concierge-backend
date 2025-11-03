# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.routers import booking, chat, ical as ical_router, notify


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="Concierge AI Agent", version="0.0.1")

    # CORS per permettere al widget di chiamare l’API da fuori
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],      # se vuoi puoi restringere dopo
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # rotte API
    app.include_router(booking.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(ical_router.router, prefix="/api")
    app.include_router(notify.router, prefix="/api")

    # statici: /static/... leggerà dalla cartella public
    app.mount("/static", StaticFiles(directory="public"), name="static")

    @app.get("/")
    def root():
        return {"ok": True, "msg": "Concierge backend up"}

    return app


app = create_app()
