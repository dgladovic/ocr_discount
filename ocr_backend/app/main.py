import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import (
    health, retailers, store_products, canonical_products, 
    price_offers, ingestion, announcements, overrides, users
)

app = FastAPI(
    title="Retail Offers API",
    description="API for fetching retail offers, store products, and canonical listings.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist and mount static files
os.makedirs("cropped_images", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

app.mount("/cropped_images", StaticFiles(directory="cropped_images"), name="cropped_images")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads") # <--- Mount downloads folder

# Register Routers
app.include_router(health.router)
app.include_router(retailers.router)
app.include_router(store_products.router)
app.include_router(canonical_products.router)
app.include_router(price_offers.router)
app.include_router(ingestion.router)
app.include_router(announcements.router)
app.include_router(overrides.router)
app.include_router(users.router)