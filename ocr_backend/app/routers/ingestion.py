from fastapi import APIRouter
from app.database import fetch_query

router = APIRouter(tags=["Ingestion"])

@router.get("/ingestion-status")
def get_ingestion_status():
    """Fetch status of recent download and extraction runs per retailer."""
    query_logs = """
        SELECT id, retailer_code, file_name, status, page_count, offer_count, error_message, attempted_at
        FROM ingestion_logs
        ORDER BY attempted_at DESC
        LIMIT 50;
    """
    logs = fetch_query(query_logs)
    
    retailer_summary = {}
    for log in logs:
        rcode = log["retailer_code"]
        if rcode not in retailer_summary:
            retailer_summary[rcode] = log
            
    return {
        "latest_by_retailer": list(retailer_summary.values()),
        "recent_logs": logs
    }