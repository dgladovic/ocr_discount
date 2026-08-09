from fastapi import APIRouter
router = APIRouter(tags=["Health"])

@router.get("/")
def health_check():
    return {"status": "ok", "message": "Retail Offers API is active"}