from fastapi import APIRouter, Query
from app.database import fetch_query
router = APIRouter(tags=["Users & Watchlist"])

@router.get("/users")
def get_users(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return fetch_query("SELECT id, email FROM users ORDER BY email ASC LIMIT %s OFFSET %s;", (limit, offset))

@router.get("/watchlist-items")
def get_watchlist_items(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), user_id: str | None = None):
    if user_id:
        return fetch_query("SELECT * FROM watchlist_items WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;", (user_id, limit, offset))
    return fetch_query("SELECT * FROM watchlist_items ORDER BY created_at DESC LIMIT %s OFFSET %s;", (limit, offset))