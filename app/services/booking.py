# app/routers/booking.py
from fastapi import APIRouter

router = APIRouter()

# --- endpoint base ---
@router.get("/health")
def health():
    return {"status": "ok"}

# --- DEBUG SHEET (solo per test) ---
@router.get("/debug-sheet")
def debug_sheet():
    try:
        from app.services import sheets
        rows = sheets.list_rows()
        return {"rows": rows}
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/_debug/env")
def debug_env():
    # leggiamo le variabili come le vede l'app
    from app.config import get_settings
    s = get_settings()
    sa = s.GOOGLE_SERVICE_ACCOUNT_JSON
    return {
        "sheet_id_present": bool(s.GOOGLE_SHEET_ID),
        "sa_email": sa.get("client_email"),
        "project_id": sa.get("project_id"),
        "has_private_key": bool(sa.get("private_key")),
        "private_key_head": (sa.get("private_key") or "")[:30]
    }

