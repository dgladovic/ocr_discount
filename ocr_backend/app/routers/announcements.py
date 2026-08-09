from fastapi import APIRouter, Query
from app.database import fetch_query
router = APIRouter(tags=["Announcements"])

@router.get("/category-announcements")
def get_category_announcements(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return fetch_query("SELECT * FROM category_announcements ORDER BY week_start DESC LIMIT %s OFFSET %s;", (limit, offset))