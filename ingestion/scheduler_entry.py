"""
Long-lived process for the ingestion container: runs the weekly pipeline on
a schedule and stays up in between (matches docker-compose's `restart: always`
expectation for a service, rather than a one-shot job that exits).

Configurable via env:
  INGESTION_SCHEDULE_DAY   default 'monday'  (day flyers typically go live)
  INGESTION_SCHEDULE_TIME  default '05:00'
  RUN_ON_STARTUP           default 'false'   set 'true' to also run immediately on boot
"""
import os
import time
import schedule

from ingestion.product_orchestrator import run

SCHEDULE_DAY = os.environ.get("INGESTION_SCHEDULE_DAY", "monday").lower()
SCHEDULE_TIME = os.environ.get("INGESTION_SCHEDULE_TIME", "05:00")
RUN_ON_STARTUP = os.environ.get("RUN_ON_STARTUP", "false").lower() == "true"


def _register_weekly_job():
    day_methods = {
        "monday": schedule.every().monday, "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday, "thursday": schedule.every().thursday,
        "friday": schedule.every().friday, "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }
    if SCHEDULE_DAY not in day_methods:
        raise ValueError(f"Invalid INGESTION_SCHEDULE_DAY: {SCHEDULE_DAY}")
    day_methods[SCHEDULE_DAY].at(SCHEDULE_TIME).do(run)


def main():
    print(f"Ingestion worker started. Scheduled for every {SCHEDULE_DAY} at {SCHEDULE_TIME}.")
    _register_weekly_job()

    if RUN_ON_STARTUP:
        print("RUN_ON_STARTUP=true, running pipeline immediately...")
        run()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()