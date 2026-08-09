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

# Configurable Gemini vision chunk sizes per retailer to avoid 503 API timeouts on dense flyers
RETAILER_CHUNK_SIZES = {
    "lidl": 6,       
    "hofer": 8,
    "billa": 8,
    "billa_plus": 8,
    "spar": 8,
    "interspar": 8,
    "penny": 8,
    "default": 8,
}


def fetch_all() -> tuple[list[str], set[str]]:
    """Fetch all current flyers and clean up expired PDFs.
    
    Returns:
        (valid_pdf_paths, current_stems) where current_stems is the set of
        PDF filename stems (without .pdf) for the flyers fetched this run.
        Pass current_stems to cleanup_stale_json() after load_all() completes.
    """
    valid_pdf_paths = []
    current_stems: set[str] = set()

    # 1. Fetch active PDFs
    for retailer_code, downloader in DOWNLOADERS.items():
        try:
            path = downloader.fetch()
            if path and os.path.exists(path):
                abs_path = os.path.abspath(path)
                valid_pdf_paths.append(abs_path)
                current_stems.add(os.path.splitext(os.path.basename(path))[0])
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

    return valid_pdf_paths, current_stems


def cleanup_stale_json(current_stems: set[str], json_dir: str = "extracted_json") -> None:
    """Delete extracted_json/*.json files that are no longer backed by a current PDF.
    
    This must be called AFTER load_all() so that every JSON has already been
    persisted to Postgres before deletion.
    
    Args:
        current_stems: Set of PDF filename stems (without extension) fetched this run.
                       e.g. {'billa_2026-08-12_billaflugblatt', 'hofer_2026-08-13_flugblatt'}
        json_dir:      Path to the extracted_json directory.
    """
    if not current_stems:
        print("[cleanup] No current stems provided — skipping JSON cleanup to be safe.")
        return

    if not os.path.isdir(json_dir):
        return

    print(f"\n--- Cleaning up stale JSON files (keeping {len(current_stems)} current) ---")
    for filename in os.listdir(json_dir):
        if not filename.lower().endswith(".json"):
            continue
        stem = os.path.splitext(filename)[0]
        if stem not in current_stems:
            filepath = os.path.join(json_dir, filename)
            try:
                os.remove(filepath)
                print(f"Deleted stale JSON: {filename}")
            except Exception as e:
                print(f"Error deleting {filename}: {e}")
        else:
            print(f"Keeping current JSON: {filename}")

if __name__ == "__main__":
    fetch_all()