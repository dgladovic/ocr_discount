"""
The single entry point the scheduled container service calls once a week:

    python -m ingestion.run_weekly_pipeline

Chains: fetch flyers -> Gemini extraction -> image cropping -> DB load.
Each stage is independently re-runnable (idempotent), so a failure partway
through doesn't corrupt state -- just re-run the whole thing once the cause
is fixed, per specs/02-ingestion.md's acceptance criteria.
"""
import sys
import traceback

from ingestion.downloaders.config import fetch_all, cleanup_stale_json
from ingestion.pdf_extractor import process_all_flyers
from ingestion.crop_images import main as crop_all
from ingestion.load_to_db import main as load_all


def run():
    current_stems: set[str] = set()

    print("=" * 60)
    print("STAGE 1/5: fetching flyers")
    print("=" * 60)
    try:
        downloaded, current_stems = fetch_all()
        print(f"Auto-downloaded {len(downloaded)} flyer(s).")
    except Exception as e:
        print(f"Stage 1 Warning: Flyer fetching encountered error: {e}")

    print("=" * 60)
    print("STAGE 2/5: Gemini extraction")
    print("=" * 60)
    try:
        process_all_flyers()
    except Exception as e:
        print(f"Stage 2 Warning: Extraction stage encountered error: {e}")

    print("=" * 60)
    print("STAGE 3/5: cropping verification images")
    print("=" * 60)
    try:
        crop_all()
    except Exception as e:
        print(f"Stage 3 Warning: Cropping stage encountered error: {e}")

    print("=" * 60)
    print("STAGE 4/5: loading into Postgres")
    print("=" * 60)
    try:
        load_all()
    except Exception as e:
        print(f"Stage 4 Warning: Database loading stage encountered error: {e}")

    print("=" * 60)
    print("STAGE 5/5: cleaning up stale intermediate files")
    print("=" * 60)
    try:
        cleanup_stale_json(current_stems)
    except Exception as e:
        print(f"Stage 5 Warning: JSON cleanup encountered error: {e}")

    print("=" * 60)
    print("Weekly pipeline run complete.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        # Container keeps running (it's a long-lived scheduled process) --
        # log loudly and let next week's scheduled run try again, rather
        # than crash-looping the whole service over one bad flyer.
        print("PIPELINE RUN FAILED:", file=sys.stderr)
        traceback.print_exc()