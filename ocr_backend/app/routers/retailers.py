from fastapi import APIRouter
from app.database import fetch_query
router = APIRouter(tags=["Retailers"])

@router.get("/retailers")
def get_retailers():
    return fetch_query("SELECT id, name, code FROM retailers ORDER BY name ASC;")