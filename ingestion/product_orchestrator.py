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

from ingestion.downloaders.config import fetch_all
from ingestion.pdf_extractor import process_all_flyers
from ingestion.crop_images import main as crop_all
from ingestion.load_to_db import main as load_all


def run():
    print("=" * 60)
    print("STAGE 1/4: fetching flyers")
    print("=" * 60)
    downloaded = fetch_all()
    print(f"Auto-downloaded {len(downloaded)} flyer(s). "
          f"Any retailer without a confirmed URL needs a manual drop into downloads/.")

    print("=" * 60)
    print("STAGE 2/4: Gemini extraction")
    print("=" * 60)
    process_all_flyers()

    print("=" * 60)
    print("STAGE 3/4: cropping verification images")
    print("=" * 60)
    crop_all()

    print("=" * 60)
    print("STAGE 4/4: loading into Postgres")
    print("=" * 60)
    load_all()

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