from fastapi import APIRouter
router = APIRouter(tags=["booking"])

@router.get("/health")
def health():
    return {"status": "ok", "area": "booking"}

# --- DEBUG SHEET ---
@router.get("/debug-sheet")
def debug_sheet():
    """
    Legge tutte le righe del foglio Bookings.
    Solo per test: rimuovere in produzione.
    """
    try:
        from app.services import sheets
        rows = sheets._ws().get_all_records()
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


@router.post("/_debug/append-sample")
def debug_append_sample():
    from app.services import sheets
    sample = {
        "property_id": "CT-01",
        "booking_ref": "TEST-001",
        "source_portal": "manual",
        "checkin_date": "2025-12-10",
        "checkin_time": "12:00",
        "checkout_date": "2025-12-13",
        "checkout_time": "10:00",
        "guest_first_name": "Mario",
        "guest_last_name": "Rossi",
        "guest_email": "mario.rossi@example.com",
        "locale": "it",
        "status": "confirmed",
        "authorized": "no",
        "wifi_coupon": "MyWifi",
        "checkin_code": "1234",
        "notes": "riga di test",
        "allow_web": "true"
    }
    sheets.append_row_dict(sample)
    return {"ok": True, "inserted": sample}

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MatchGuestReq(BaseModel):
    arrival_date: str = Field(..., description="Data arrivo, es. 2025-12-10 o 10/12/2025")
    last_name: str = Field(..., description="Cognome")
    first_name: Optional[str] = Field(None, description="Nome (opzionale)")
    property_id: Optional[str] = Field(None, description="ID proprietà (opzionale)")

class MatchGuestRes(BaseModel):
    status: str
    message: Optional[str] = None
    row_index: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

@router.post("/match-guest", response_model=MatchGuestRes)
def match_guest(req: MatchGuestReq):
    """
    Trova la prenotazione nel tab 'Bookings' a partire da data arrivo + cognome
    (opzionalmente anche nome e/o property_id).
    """
    from app.services.sheets import find_booking, read_row_by_index

    row_index, row_dict, count = find_booking(
        arrival_date=req.arrival_date,
        last_name=req.last_name,
        first_name=req.first_name,
        property_id=req.property_id,
    )

    if count == 0:
        return MatchGuestRes(status="not_found", message="Nessuna prenotazione trovata.")
    if count > 1:
        return MatchGuestRes(
            status="ambiguous",
            message=f"Sono state trovate {count} prenotazioni: specifica anche nome o property_id."
        )

    # 1 match: ricarichiamo la riga “viva” per sicurezza
    data = read_row_by_index(row_index)
    return MatchGuestRes(status="ok", row_index=row_index, data=data)

class GuestRegisterReq(BaseModel):
    arrival_date: str
    last_name: str
    first_name: str
    guest_email: Optional[str] = None
    property_id: Optional[str] = None
    locale: Optional[str] = "it"
    phone: Optional[str] = None
    checkout_date: Optional[str] = None
    notes: Optional[str] = None

class GuestRegisterRes(BaseModel):
    status: str
    action: str
    data: Dict[str, Any]
    notification: Optional[str] = None

@router.post("/guest/register", response_model=GuestRegisterRes)
def guest_register(req: GuestRegisterReq):
    """
    Registra o aggiorna un ospite nel tab 'Bookings'.
    Se trova una riga corrispondente → aggiorna.
    Altrimenti crea nuova riga.
    """
    from app.services import sheets

    notes = req.notes or ""
    if req.phone:
        phone_note = f"Telefono ospite: {req.phone}"
        if phone_note not in notes:
            notes = (notes + "\n" if notes else "") + phone_note

    payload = {
        "property_id": req.property_id or "CT-01",
        "checkin_date": req.arrival_date,
        "checkout_date": req.checkout_date or "",
        "guest_last_name": req.last_name,
        "guest_first_name": req.first_name,
        "guest_email": req.guest_email or "",
        "guest_phone": req.phone or "",
        "locale": req.locale,
        "notes": notes,
        "status": "pending",
        "authorized": "no"
    }

    result = sheets.upsert_booking(req.arrival_date, req.last_name, req.first_name, payload)
    
    notification_msg = None
    from app.config import get_settings
    settings = get_settings()
    host_emails = settings.HOST_NOTIFICATION_EMAILS

    if host_emails:
        try:
            from app.services.mail import send_email
            from app.services.templates import host_authorization_email

            subject, html = host_authorization_email(result["data"])
            for email in host_emails:
                send_email(email, subject, html)
            notification_msg = f"Notifica inviata all'host ({', '.join(host_emails)})."
        except Exception as e:
            notification_msg = f"Errore invio email host: {e}"
    else:
        notification_msg = "Email host non configurata: nessuna notifica inviata."

    return GuestRegisterRes(status="ok", action=result["action"], data=result["data"], notification=notification_msg)

class HostAuthorizeReq(BaseModel):
    arrival_date: str
    last_name: str
    first_name: str
    checkin_code: str
    wifi_coupon: str
    notes: Optional[str] = None

class HostAuthorizeRes(BaseModel):
    status: str
    message: Optional[str] = None
    row_index: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

@router.post("/host/authorize", response_model=HostAuthorizeRes)
def host_authorize(req: HostAuthorizeReq):
    """
    L'host autorizza un ospite: aggiorna la riga con authorized=yes,
    scrive checkin_code e wifi_coupon, e invia email al guest se presente.
    """
    from app.services.sheets import authorize_guest
    result = authorize_guest(
        arrival_date=req.arrival_date,
        last_name=req.last_name,
        first_name=req.first_name,
        checkin_code=req.checkin_code,
        wifi_coupon=req.wifi_coupon,
        notes=req.notes or "",
    )

    if result.get("status") != "ok":
        return HostAuthorizeRes(**result)

    # Invio email al guest (se ha una email)
    row = result.get("data") or {}
    guest_email = (row.get("guest_email") or "").strip()
    locale = (row.get("locale") or "it").lower()

    email_error = None
    if guest_email:
        try:
            from app.services.mail import send_email
            from app.services.templates import activation_email
            subject, html = activation_email(row, locale)
            send_email(guest_email, subject, html)
        except Exception as e:
            email_error = str(e)

    # arricchiamo la risposta con l'esito dell'invio email
    out = HostAuthorizeRes(**result)
    if email_error:
        out.message = (out.message + " | " if out.message else "") + f"Email non inviata: {email_error}"
    else:
        out.message = (out.message + " | " if out.message else "") + ("Email inviata a " + guest_email if guest_email else "Nessuna email guest disponibile")
    return out

