# app/services/sheets.py
"""Utility per la gestione delle prenotazioni su Google Sheet o file Excel."""

from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

try:  # pragma: no cover - import opzionale
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
except Exception:  # pragma: no cover - ambiente senza dipendenze Google
    gspread = None  # type: ignore
    Credentials = None  # type: ignore
if TYPE_CHECKING:  # pragma: no cover - solo per i type checker
    from gspread import Client as GSpreadClient
else:  # pragma: no cover - a runtime non abbiamo bisogno del tipo
    GSpreadClient = Any
from app.config import get_settings

# Scope minimo per leggere/scrivere Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

BOOKINGS_EXCEL_PATH = os.getenv(
    "BOOKINGS_EXCEL_PATH",
    os.path.join(os.getcwd(), "Bookings.xlsx"),
)
BOOKINGS_SHEET_NAME = os.getenv("BOOKINGS_SHEET_NAME", "Bookings")

_BACKEND: Optional[str] = None  # "google" oppure "excel"


# ---------------------------------------------------------------------------
# Determinazione backend
# ---------------------------------------------------------------------------


def _determine_backend() -> str:
    """Determina se usare Google Sheets o il file Excel locale."""

    global _BACKEND
    if _BACKEND:
        return _BACKEND

    excel_available = os.path.exists(BOOKINGS_EXCEL_PATH)
    settings = get_settings()
    google_ready = bool(gspread and Credentials and settings.GOOGLE_SHEET_ID)

    # Preferiamo il file Excel se disponibile (richiesta progetto)
    if excel_available:
        _BACKEND = "excel"
        return _BACKEND

    if google_ready:
        _BACKEND = "google"
        return _BACKEND

    raise RuntimeError(
        "Nessun backend prenotazioni disponibile: fornisci GOOGLE_SHEET_ID oppure il file Bookings.xlsx"
    )

    # ---------------------------------------------------------------------------
# Backend Google Sheets (utilizzato solo se configurato)
# ---------------------------------------------------------------------------


def _google_client() -> GSpreadClient:  # pragma: no cover - dipende da Google
    if not gspread or not Credentials:
        raise RuntimeError("gspread non disponibile")

    settings = get_settings()

    sa = dict(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    pk = sa.get("private_key", "")
    if "\\n" in pk:
        sa["private_key"] = pk.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return gspread.authorize(creds)

def _google_ws():  # pragma: no cover - dipende da Google
    settings = get_settings()
    gc = _google_client()
    sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
    return sh.worksheet(BOOKINGS_SHEET_NAME)


def _google_headers(ws):  # pragma: no cover
    return ws.row_values(1)


def _google_list_rows() -> List[Dict[str, Any]]:  # pragma: no cover
    ws = _google_ws()
    return ws.get_all_records()


def _google_append_row_dict(data: dict) -> None:  # pragma: no cover
    ws = _google_ws()
    headers = ws.row_values(1)
    if not headers:
        raise RuntimeError("Il worksheet 'Bookings' non ha header nella riga 1.")

    row = [str(data.get(h, "")) if data.get(h) is not None else "" for h in headers]
    ws.append_row(row, value_input_option="RAW")

def _google_row_by_index(row_index: int) -> Dict[str, Any]:  # pragma: no cover
    ws = _google_ws()
    headers = _google_headers(ws)
    values = ws.row_values(row_index)
    values += [""] * (len(headers) - len(values))
    return {h: values[i] if i < len(values) else "" for i, h in enumerate(headers)}


def _google_update_row_dict(row_index: int, data: dict) -> None:  # pragma: no cover
    ws = _google_ws()
    headers = ws.row_values(1)
    row = ws.row_values(row_index)
    row += [""] * (len(headers) - len(row))

    for i, h in enumerate(headers):
        if h in data:
            row[i] = str(data[h]) if data[h] is not None else ""

    ws.update(
        f"A{row_index}:{chr(64 + len(headers))}{row_index}",
        [row],
        value_input_option="RAW",
    )


# ---------------------------------------------------------------------------
# Backend Excel
# ---------------------------------------------------------------------------


EXCEL_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _excel_zip() -> zipfile.ZipFile:
    if not os.path.exists(BOOKINGS_EXCEL_PATH):
        raise RuntimeError(f"File Excel non trovato: {BOOKINGS_EXCEL_PATH}")
    return zipfile.ZipFile(BOOKINGS_EXCEL_PATH, "r")


def _excel_sheet_path(zf: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    target = None
    for sheet in workbook.findall("main:sheets/main:sheet", EXCEL_NS):
        name = sheet.get("name")
        if name == BOOKINGS_SHEET_NAME:
            rid = sheet.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            for rel in rels.findall(
                "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
            ):
                if rel.get("Id") == rid:
                    target = rel.get("Target")
                    break
    if not target:
        raise RuntimeError(f"Sheet '{BOOKINGS_SHEET_NAME}' non trovato nel file Excel")
    if not target.startswith("xl/"):
        target = f"xl/{target}"
    return target


def _excel_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    strings: List[str] = []
    for si in root.findall("main:si", EXCEL_NS):
        parts = [t.text or "" for t in si.findall(".//main:t", EXCEL_NS)]
        strings.append("".join(parts))
    return strings


def _excel_extract_rows() -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    with _excel_zip() as zf:
        sheet_path = _excel_sheet_path(zf)
        shared = _excel_shared_strings(zf)
        sheet_root = ET.fromstring(zf.read(sheet_path))

    header_map: Dict[str, str] = {}
    records: List[Dict[str, Any]] = []

    sheet_data = sheet_root.find("main:sheetData", EXCEL_NS)
    if sheet_data is None:
        return header_map, records

    for row in sheet_data.findall("main:row", EXCEL_NS):
        row_index = int(row.get("r"))
        cells: Dict[str, str] = {}
        for cell in row.findall("main:c", EXCEL_NS):
            ref = cell.get("r", "")
            col = "".join(ch for ch in ref if ch.isalpha())
            value = ""
            c_type = cell.get("t")
            if c_type == "s":
                v = cell.find("main:v", EXCEL_NS)
                if v is not None and v.text:
                    value = shared[int(v.text)]
            elif c_type == "inlineStr":
                value = "".join(
                    (t_el.text or "") for t_el in cell.findall("main:is/main:t", EXCEL_NS)
                )
            else:
                v = cell.find("main:v", EXCEL_NS)
                if v is not None and v.text is not None:
                    value = v.text

            cells[col] = value

        if row_index == 1:
            header_map = {
                col: cells[col]
                for col in sorted(cells.keys(), key=lambda x: (len(x), x))
            }
            continue

        if not header_map:
            continue

        record: Dict[str, Any] = {"_row_index": row_index}
        for col, header in header_map.items():
            record[header] = cells.get(col, "")
        records.append(_excel_post_process_record(record))

    return header_map, records


def _excel_post_process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("checkin_date", "checkout_date"):
        record[key] = _normalize_date_value(record.get(key, ""))
    return record


def _excel_list_rows() -> List[Dict[str, Any]]:
    _, records = _excel_extract_rows()
    cleaned: List[Dict[str, Any]] = []
    for rec in records:
        rec = dict(rec)
        rec.pop("_row_index", None)
        cleaned.append(rec)
    return cleaned


def _excel_row_by_index(row_index: int) -> Dict[str, Any]:
    _, records = _excel_extract_rows()
    for rec in records:
        if rec.get("_row_index") == row_index:
            rec = dict(rec)
            rec.pop("_row_index", None)
            return rec
    raise IndexError(f"Riga {row_index} non trovata nel file Excel")


def _excel_update_row_dict(row_index: int, data: dict) -> None:
    with _excel_zip() as zf:
        sheet_path = _excel_sheet_path(zf)
        sheet_root = ET.fromstring(zf.read(sheet_path))
        header_map, _ = _excel_extract_rows()

    if not header_map:
        raise RuntimeError("Header del foglio non trovato")

    sheet_data = sheet_root.find("main:sheetData", EXCEL_NS)
    if sheet_data is None:
        raise RuntimeError("sheetData non presente nel foglio Excel")

    row_elem = None
    for row in sheet_data.findall("main:row", EXCEL_NS):
        if int(row.get("r")) == row_index:
            row_elem = row
            break
    if row_elem is None:
        raise IndexError(f"Riga {row_index} non trovata")

    def ensure_cell(column: str):
        cell_ref = f"{column}{row_index}"
        for cell in row_elem.findall("main:c", EXCEL_NS):
            if cell.get("r") == cell_ref:
                return cell
        cell = ET.SubElement(
            row_elem, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
        )
        cell.set("r", cell_ref)
        return cell

    for header, value in data.items():
        if header not in header_map.values():
            continue
        column = next(col for col, name in header_map.items() if name == header)
        cell = ensure_cell(column)
        for child in list(cell):
            cell.remove(child)
        if value in (None, ""):
            cell.attrib.pop("t", None)
            continue
        cell.set("t", "inlineStr")
        is_elem = ET.SubElement(
            cell, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is"
        )
        t_elem = ET.SubElement(
            is_elem, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
        )
        t_elem.text = str(value)

    _excel_write_sheet(sheet_root, sheet_path)


def _excel_append_row_dict(data: dict) -> None:
    with _excel_zip() as zf:
        sheet_path = _excel_sheet_path(zf)
        sheet_root = ET.fromstring(zf.read(sheet_path))
        header_map, records = _excel_extract_rows()

    if not header_map:
        raise RuntimeError("Header del foglio non trovato")

    sheet_data = sheet_root.find("main:sheetData", EXCEL_NS)
    if sheet_data is None:
        raise RuntimeError("sheetData non presente nel foglio Excel")

    new_index = 2 + len(records)
    row_elem = ET.SubElement(
        sheet_data, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"
    )
    row_elem.set("r", str(new_index))

    for col, header in header_map.items():
        value = data.get(header, "")
        if value in (None, ""):
            continue
        cell = ET.SubElement(
            row_elem, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
        )
        cell.set("r", f"{col}{new_index}")
        cell.set("t", "inlineStr")
        is_elem = ET.SubElement(
            cell, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is"
        )
        t_elem = ET.SubElement(
            is_elem, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
        )
        t_elem.text = str(value)

    dimension = sheet_root.find("main:dimension", EXCEL_NS)
    if dimension is not None and header_map:
        start_col = next(iter(header_map.keys()))
        end_col = list(header_map.keys())[-1]
        dimension.set("ref", f"{start_col}1:{end_col}{new_index}")

    _excel_write_sheet(sheet_root, sheet_path)


def _excel_write_sheet(sheet_root: ET.Element, sheet_path: str) -> None:
    xml_bytes = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
    with _excel_zip() as zf:
        existing = {
            item.filename: zf.read(item.filename)
            for item in zf.infolist()
            if item.filename != sheet_path
        }

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, "w") as zout:
            for filename, data in existing.items():
                zout.writestr(filename, data)
            zout.writestr(sheet_path, xml_bytes)
        os.replace(tmp_path, BOOKINGS_EXCEL_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Funzioni comuni / API pubblica
# ---------------------------------------------------------------------------


def list_rows() -> List[Dict[str, Any]]:
    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        return _google_list_rows()
    return _excel_list_rows()


def append_row_dict(data: dict) -> None:
    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        _google_append_row_dict(data)
    else:
        _excel_append_row_dict(data)


def read_row_by_index(row_index: int) -> Dict[str, Any]:
    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        return _google_row_by_index(row_index)
    return _excel_row_by_index(row_index)


def update_row_dict(row_index: int, data: dict) -> None:
    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        _google_update_row_dict(row_index, data)
    else:
        _excel_update_row_dict(row_index, data)


# ---------------------------------------------------------------------------
# Funzioni di ricerca/aggiornamento prenotazioni
# ---------------------------------------------------------------------------



def _normalize_name(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _parse_date_any(s: str) -> str:
    """Restituisce la data in formato ISO YYYY-MM-DD."""
    
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s

def _normalize_date_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        base = datetime(1899, 12, 30)
        try:
            as_date = base + timedelta(days=float(value))
            return as_date.strftime("%Y-%m-%d")
        except Exception:
            return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return ""
    if any(sep in text for sep in ("-", "/")):
        return _parse_date_any(text)
    try:
        num = float(text)
        base = datetime(1899, 12, 30)
        as_date = base + timedelta(days=num)
        return as_date.strftime("%Y-%m-%d")
    except Exception:
        return _parse_date_any(text)

def find_booking(
    arrival_date: str,
    last_name: str,
    first_name: Optional[str] = None,
    property_id: Optional[str] = None,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], int]:

    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        ws = _google_ws()
        records = [
            {**rec, "_row_index": idx}
            for idx, rec in enumerate(ws.get_all_records(), start=2)
        ]
    else:
        _, records = _excel_extract_rows()

    want_date = _parse_date_any(arrival_date)
    want_ln = _normalize_name(last_name)
    want_fn = _normalize_name(first_name)
    want_pid = (property_id or "").strip()

    hits: List[Tuple[int, Dict[str, Any]]] = []
    for rec in records:
        idx = rec.get("_row_index") or records.index(rec) + 2
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
        idx, rec = hits[0]
        rec = dict(rec)
        rec.pop("_row_index", None)
        return idx, rec, 1
    if len(hits) == 0:
        return None, None, 0
    
    return None, None, len(hits)

def upsert_booking(arrival_date: str, last_name: str, first_name: str, payload: dict) -> dict:
    
    idx, rec, count = find_booking(arrival_date, last_name, first_name)
    backend = _determine_backend()

    if backend == "google":  # pragma: no cover
        ws = _google_ws()
        headers = _google_headers(ws)
    else:
        header_map, _ = _excel_extract_rows()
        headers = list(header_map.values())

    if count == 1 and idx:
        update_row_dict(idx, payload)
        return {"action": "updated", "row_index": idx, "data": read_row_by_index(idx)}
    
    if backend == "google":  # pragma: no cover
        row = [str(payload.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="RAW")
    else:
        _excel_append_row_dict(payload)
    
    return {"action": "inserted", "row_index": None, "data": payload}

def authorize_guest(
    arrival_date: str,
    last_name: str,
    first_name: str,
    checkin_code: str,
    wifi_coupon: str,
    notes: str = "",
) -> dict:
   
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
        "notes": notes or (rec or {}).get("notes", ""),
    }
    update_row_dict(idx, payload)
    return {"status": "ok", "row_index": idx, "data": read_row_by_index(idx)}

# ---------------------------------------------------------------------------
# Funzioni aggiuntive per chatbot
# ---------------------------------------------------------------------------


def list_incomplete_bookings(property_id: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list_rows()
    filtered: List[Dict[str, Any]] = []
    for rec in rows:
        if property_id and (rec.get("property_id") or "").strip() != property_id.strip():
            continue
        if (
            not rec.get("guest_first_name")
            or not rec.get("guest_last_name")
            or not rec.get("guest_email")
        ):
            filtered.append(rec)
    return filtered


def find_booking_by_dates(
    arrival_date: str,
    departure_date: Optional[str],
    property_id: Optional[str] = None,
    require_missing_details: bool = False,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], int]:
    backend = _determine_backend()
    if backend == "google":  # pragma: no cover
        ws = _google_ws()
        raw_records = [
            {**rec, "_row_index": idx}
            for idx, rec in enumerate(ws.get_all_records(), start=2)
        ]
    else:
        _, raw_records = _excel_extract_rows()

    want_arrival = _parse_date_any(arrival_date)
    want_departure = _parse_date_any(departure_date or "")
    want_pid = (property_id or "").strip()

    hits: List[Dict[str, Any]] = []
    for rec in raw_records:
        r_pid = (rec.get("property_id") or "").strip()
        if property_id and r_pid != want_pid:
            continue
        r_arrival = _parse_date_any(str(rec.get("checkin_date", "")))
        r_departure = _parse_date_any(str(rec.get("checkout_date", "")))
        if r_arrival != want_arrival:
            continue
        if departure_date and r_departure != want_departure:
            continue
        if require_missing_details and not (
            not rec.get("guest_first_name")
            or not rec.get("guest_last_name")
            or not rec.get("guest_email")
        ):
            continue
        hits.append(rec)

    if len(hits) == 1:
        idx = hits[0].get("_row_index")
        rec = dict(hits[0])
        if "_row_index" in rec:
            rec.pop("_row_index")
        return idx, rec, 1
    return None, None, len(hits)