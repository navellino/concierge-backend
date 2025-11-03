from fastapi import APIRouter
router = APIRouter(tags=["notify"])

@router.get("/notify/ping")
def ping():
    return {"pong": True}
