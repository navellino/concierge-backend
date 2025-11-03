from fastapi import APIRouter
from pydantic import BaseModel
from app.services import kb

router = APIRouter(tags=["chat"])

class ChatReq(BaseModel):
    message: str
    propertyId: str = "CT-01"
    locale: str = "it"

@router.post("/chat")
def chat(req: ChatReq):
    text = req.message.lower().strip()
    if "wifi" in text or "wi-fi" in text:
        info = kb.get_wifi(req.propertyId, req.locale)
        if info:
            msg = f"Wi-Fi: SSID {info['ssid']}; password {info['password']}."
            if info.get("note"):
                msg += f" {info['note']}"
            return {"text": msg}
        return {"text": "Non ho i dati Wi-Fi in archivio per questa struttura."}
    return {"text": "Posso aiutarti con Wi-Fi, check-in, emergenze. Scrivi 'wifi' per iniziare."}
