import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder
from app.database import get_db_cursor

router = APIRouter(prefix="/users", tags=["Users"])


class UserCreateSchema(BaseModel):
    email: str = Field(..., example="admin@retailoffers.com")


@router.get("")
def list_users():
    """Returns all registered users with their watchlist count."""
    query = """
        SELECT 
            u.id, 
            u.email,
            COUNT(wi.id) AS watched_products_count
        FROM users u
        LEFT JOIN watchlist_items wi ON wi.user_id = u.id
        GROUP BY u.id, u.email
        ORDER BY u.email ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        return jsonable_encoder(rows)


@router.get("/current")
def get_current_user():
    """Returns the current admin user."""
    with get_db_cursor() as cur:
        cur.execute("SELECT id, email FROM users WHERE email = 'admin@retailoffers.com' LIMIT 1;")
        user = cur.fetchone()
        if not user:
            # Fallback to first user in table
            cur.execute("SELECT id, email FROM users ORDER BY email ASC LIMIT 1;")
            user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="No users found in database.")
        return jsonable_encoder(user)


@router.post("")
def create_user(payload: UserCreateSchema):
    """
    Creates a new user via API.
    If the email already exists, it returns the existing user.
    """
    email_clean = payload.email.strip().lower()

    # Basic regex validation so we don't need the 'email-validator' package
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email_clean):
        raise HTTPException(status_code=400, detail="Invalid email format")

    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (email) 
            VALUES (%s) 
            ON CONFLICT (email) 
            DO UPDATE SET email = EXCLUDED.email 
            RETURNING id, email;
            """,
            (email_clean,)
        )
        user = cur.fetchone()
        return jsonable_encoder(user)