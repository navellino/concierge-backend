from fastapi import APIRouter
router = APIRouter(tags=["ical"])

@router.get("/ical/ping")
def ping():
    return {"pong": True}
