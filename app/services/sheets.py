# app/services/sheets.py
import gspread
from google.oauth2.service_account import Credentials
from app.config import get_settings

# Scope minimo per leggere/scrivere Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _client() -> gspread.Client:
    s = get_settings()

    # Copia il dict e converti '\n' testuali in newline reali
    sa = dict(s.GOOGLE_SERVICE_ACCOUNT_JSON)
    pk = sa.get("private_key", "")
    if "\\n" in pk:
        sa["private_key"] = pk.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return gspread.authorize(creds)

def _ws():
    """
    Restituisce il Worksheet 'Bookings' del Google Sheet
    indicato in GOOGLE_SHEET_ID.
    """
    s = get_settings()
    gc = _client()
    sh = gc.open_by_key(s.GOOGLE_SHEET_ID)
    return sh.worksheet("Bookings")

def list_rows():
    """
    Ritorna tutte le righe (come lista di dict) del worksheet.
    Serve solo per il test di collegamento.
    """
    ws = _ws()
    return ws.get_all_records()  # ogni riga diventa un dict {colonna: valore}

def append_row_dict(data: dict) -> None:
    """
    Aggiunge una riga in fondo al worksheet 'Bookings'.
    Le chiavi di 'data' devono corrispondere ai nomi colonna (riga 1).
    Le colonne mancanti vengono lasciate vuote.
    """
    ws = _ws()
    headers = ws.row_values(1)  # header dalla riga 1
    if not headers:
        raise RuntimeError("Il worksheet 'Bookings' non ha header nella riga 1.")

    # costruisci la lista valori rispettando l’ordine delle colonne
    row = [str(data.get(h, "")) if data.get(h) is not None else "" for h in headers]

    ws.append_row(row, value_input_option="RAW")

from typing import Optional, Tuple, Dict, Any
from datetime import datetime

def _headers(ws):
    return ws.row_values(1)

def _normalize_name(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _parse_date_any(s: str) -> str:
    """
    Restituisce la data in formato ISO YYYY-MM-DD anche se arriva come DD/MM/YYYY.
    Se non riconosce, ritorna la stringa originale.
    """
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s  # meglio di niente

def find_booking(
    arrival_date: str,
    last_name: str,
    first_name: Optional[str] = None,
    property_id: Optional[str] = None
) -> Tuple[Optional[int], Optional[Dict[str, Any]], int]:
    """
    Cerca una riga che combaci con:
    - checkin_date (match ISO)
    - guest_last_name (case-insensitive)
    - opzionale guest_first_name
    - opzionale property_id

    Ritorna: (row_index, row_dict, matched_count)
    - row_index è l'indice REALE nel foglio (2 = prima riga dati, perché 1 è header)
    - row_dict è la riga come dict
    - matched_count è quante righe hanno matchato (0, 1, >1)
    """
    ws = _ws()
    records = ws.get_all_records()  # list[dict], parte dalla riga 2
    want_date = _parse_date_any(arrival_date)
    want_ln = _normalize_name(last_name)
    want_fn = _normalize_name(first_name)
    want_pid = (property_id or "").strip()

    hits = []
    for idx, rec in enumerate(records, start=2):
        r_date = _parse_date_any(str(rec.get("checkin_date", "")))
        r_ln = _normalize_name(rec.get("guest_last_name"))
        r_fn = _normalize_name(rec.get("guest_first_name"))
        r_pid = (rec.get("property_id") or "").strip()

        if r_date != want_date:
            continue
        if r_ln != want_ln:
            continue
        if first_name and r_fn != want_fn:
            continue
        if property_id and r_pid != want_pid:
            continue

        hits.append((idx, rec))

    if len(hits) == 1:
        return hits[0][0], hits[0][1], 1
    elif len(hits) == 0:
        return None, None, 0
    else:
        # Ambiguità: più righe
        return None, None, len(hits)

def read_row_by_index(row_index: int) -> Dict[str, Any]:
    """
    Legge una riga precisa (indice assoluto nel foglio) e la mappa su header.
    """
    ws = _ws()
    headers = _headers(ws)
    values = ws.row_values(row_index)
    values += [""] * (len(headers) - len(values))
    return {h: values[i] if i < len(values) else "" for i, h in enumerate(headers)}

def update_row_dict(row_index: int, data: dict) -> None:
    """
    Aggiorna una riga esistente (row_index assoluto, es. 2 = prima riga dati).
    Solo le colonne che matchano gli header vengono sovrascritte.
    """
    ws = _ws()
    headers = ws.row_values(1)
    row = ws.row_values(row_index)
    row += [""] * (len(headers) - len(row))

    for i, h in enumerate(headers):
        if h in data:
            row[i] = str(data[h])

    ws.update(f"A{row_index}:{chr(64+len(headers))}{row_index}", [row], value_input_option="RAW")


def upsert_booking(arrival_date: str, last_name: str, first_name: str, payload: dict) -> dict:
    """
    Se esiste già una prenotazione con (arrival_date, last_name, first_name) → aggiorna.
    Altrimenti inserisce una nuova riga.
    """
    idx, rec, count = find_booking(arrival_date, last_name, first_name)
    ws = _ws()
    headers = ws.row_values(1)

    if count == 1 and idx:
        update_row_dict(idx, payload)
        return {"action": "updated", "row_index": idx, "data": read_row_by_index(idx)}

    # altrimenti: append nuova riga
    row = [str(payload.get(h, "")) for h in headers]
    ws.append_row(row, value_input_option="RAW")
    return {"action": "inserted", "row_index": None, "data": payload}

def authorize_guest(
    arrival_date: str,
    last_name: str,
    first_name: str,
    checkin_code: str,
    wifi_coupon: str,
    notes: str = "",
) -> dict:
    """
    Segna la prenotazione come autorizzata, scrivendo checkin_code e wifi_coupon.
    """
    idx, rec, count = find_booking(arrival_date, last_name, first_name)

    if count == 0:
        return {"status": "not_found", "message": "Prenotazione non trovata."}
    if count > 1:
        return {"status": "ambiguous", "message": "Più prenotazioni trovate, specifica meglio."}

    payload = {
        "authorized": "yes",
        "checkin_code": checkin_code,
        "wifi_coupon": wifi_coupon,
        "status": "ready",
        "notes": notes or rec.get("notes", "")
    }
    update_row_dict(idx, payload)
    return {"status": "ok", "row_index": idx, "data": read_row_by_index(idx)}