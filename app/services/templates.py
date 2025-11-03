# app/services/templates.py
from typing import Dict

def activation_email(row: Dict[str, str], locale: str = "it") -> tuple[str, str]:
    """
    Ritorna (subject, html) dell'email di attivazione concierge.
    Usa i campi presenti nella riga del foglio: guest_first_name, checkin_code, wifi_coupon, checkin_date, checkin_time, notes.
    """
    name = row.get("guest_first_name") or row.get("guest_last_name") or "Ospite"
    code = row.get("checkin_code") or "—"
    wifi = row.get("wifi_coupon") or "—"
    date = row.get("checkin_date") or ""
    time = row.get("checkin_time") or ""
    notes = row.get("notes") or ""

    if locale == "en":
        subject = "Your concierge is active – Welcome!"
        html = f"""
        <p>Hi {name},</p>
        <p>Your concierge has been activated. Here are your details:</p>
        <ul>
          <li><b>Check-in</b>: {date} {time}</li>
          <li><b>Door code</b>: {code}</li>
          <li><b>Wi-Fi coupon</b>: {wifi}</li>
        </ul>
        {"<p><i>Notes:</i> " + notes + "</p>" if notes else ""}
        <p>If you need anything, just reply to this email.</p>
        <p>Enjoy your stay!</p>
        """
        return subject, html

    if locale == "es":
        subject = "Tu concierge está activo – ¡Bienvenido!"
        html = f"""
        <p>Hola {name},</p>
        <p>Tu servicio de concierge ha sido activado. Aquí están tus datos:</p>
        <ul>
          <li><b>Check-in</b>: {date} {time}</li>
          <li><b>Código de la puerta</b>: {code}</li>
          <li><b>Cupon Wi-Fi</b>: {wifi}</li>
        </ul>
        {"<p><i>Notas:</i> " + notes + "</p>" if notes else ""}
        <p>Para cualquier cosa, responde a este correo.</p>
        <p>¡Disfruta tu estancia!</p>
        """
        return subject, html

    # IT (default)
    subject = "Il tuo concierge è attivo – Benvenuto!"
    html = f"""
    <p>Ciao {name},</p>
    <p>Il tuo concierge è stato attivato. Ecco i tuoi dettagli:</p>
    <ul>
      <li><b>Check-in</b>: {date} {time}</li>
      <li><b>Codice porta</b>: {code}</li>
      <li><b>Coupon Wi-Fi</b>: {wifi}</li>
    </ul>
    {"<p><i>Note:</i> " + notes + "</p>" if notes else ""}
    <p>Per qualsiasi necessità rispondi a questa email.</p>
    <p>Buon soggiorno!</p>
    """
    return subject, html
