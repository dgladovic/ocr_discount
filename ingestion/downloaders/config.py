import os
from ingestion.downloaders.base import ManualDropDownloader, DOWNLOAD_DIR
from ingestion.downloaders.dynamic import (
    BillaDownloader,
    LidlDownloader, 
    SparDownloader, 
    HoferDownloader, 
    PennyDownloader
)

DOWNLOADERS = {
    # Billa allows overriding the title to fetch both flyers independently
    "billa": BillaDownloader(retailer_code="billa", title="BILLA Flugblatt"),
    "billa_plus": BillaDownloader(retailer_code="billa_plus", title="BILLA PLUS Flugblatt"),
    
    # Spar dynamically takes its target URLs
    "spar": SparDownloader("spar", "https://www.spar.at/aktionen/wien/spar"),
    "interspar": SparDownloader("interspar", "https://www.spar.at/aktionen/wien/interspar"),
    
    "hofer": HoferDownloader("hofer"),
    "penny": PennyDownloader("penny"),
    "lidl": LidlDownloader  ("lidl"),
}


def fetch_all():
    valid_pdf_paths = []
    
    # 1. Fetch active PDFs
    for retailer_code, downloader in DOWNLOADERS.items():
        try:
            path = downloader.fetch()
            if path and os.path.exists(path):
                # Save the absolute path of successfully fetched PDFs
                valid_pdf_paths.append(os.path.abspath(path))
        except Exception as e:
            print(f"[{retailer_code}] Failed to fetch: {e}")

    # 2. Cleanup expired PDFs automatically
    # Anything left in the download dir that wasn't retrieved/verified today gets wiped.
    if valid_pdf_paths:
        print("\n--- Cleaning up expired PDFs ---")
        for filename in os.listdir(DOWNLOAD_DIR):
            if filename.lower().endswith(".pdf"):
                filepath = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
                if filepath not in valid_pdf_paths:
                    try:
                        os.remove(filepath)
                        print(f"Deleted expired PDF: {filename}")
                    except Exception as e:
                        print(f"Error deleting {filename}: {e}")

    return valid_pdf_paths

if __name__ == "__main__":
    fetch_all()