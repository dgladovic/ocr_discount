"""
Long-lived process for the ingestion container: runs the weekly pipeline on
a schedule and stays up in between (matches docker-compose's `restart: always`
expectation for a service, rather than a one-shot job that exits).

Configurable via env:
  INGESTION_SCHEDULE_DAY   default 'monday'  (day flyers typically go live)
  INGESTION_SCHEDULE_TIME  default '05:00'
  RUN_ON_STARTUP           default 'true'    set 'true' to run immediately on container boot
"""
import os
import sys
import time
import schedule
from datetime import datetime

from ingestion.product_orchestrator import run

SCHEDULE_DAY = os.environ.get("INGESTION_SCHEDULE_DAY", "monday").lower()
SCHEDULE_TIME = os.environ.get("INGESTION_SCHEDULE_TIME", "05:00")
# Default to "true" so the container runs processing immediately on boot!
RUN_ON_STARTUP = os.environ.get("RUN_ON_STARTUP", "true").lower() == "true"


def log(msg: str):
    """Prints a timestamped log message and flushes stdout immediately for Docker logs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def _register_weekly_job():
    day_methods = {
        "monday": schedule.every().monday,
        "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday,
        "thursday": schedule.every().thursday,
        "friday": schedule.every().friday,
        "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }
    if SCHEDULE_DAY not in day_methods:
        raise ValueError(f"Invalid INGESTION_SCHEDULE_DAY: {SCHEDULE_DAY}")
    
    day_methods[SCHEDULE_DAY].at(SCHEDULE_TIME).do(_scheduled_run)
    log(f"Registered weekly job for every {SCHEDULE_DAY.upper()} at {SCHEDULE_TIME}.")


def _scheduled_run():
    log("=== SCHEDULED TRIGGER FIRED: Running Weekly Ingestion Pipeline ===")
    try:
        run()
        log("=== Scheduled Ingestion Pipeline Complete ===")
    except Exception as e:
        log(f"!!! Scheduled Pipeline Failed with Error: {e} !!!")


def main():
    log("==================================================")
    log("INGESTION SCHEDULER SERVICE STARTED & UP")
    log(f"Config -> Schedule: {SCHEDULE_DAY.upper()} @ {SCHEDULE_TIME} | Run on Startup: {RUN_ON_STARTUP}")
    log("==================================================")

    _register_weekly_job()

    if RUN_ON_STARTUP:
        log("RUN_ON_STARTUP=true detected -> Triggering immediate pipeline execution now...")
        try:
            run()
            log("=== Initial Startup Pipeline Complete ===")
        except Exception as e:
            log(f"!!! Initial Startup Pipeline Failed: {e} !!!")
    else:
        log("RUN_ON_STARTUP=false -> Waiting for next scheduled trigger...")

    log("Scheduler entering main loop. Listening for scheduled triggers...")
    
    last_heartbeat = time.time()
    
    while True:
        schedule.run_pending()
        
        # Log a heartbeat every hour so you know the service is alive in docker logs
        if time.time() - last_heartbeat > 3600:
            log("Heartbeat: Ingestion scheduler service is healthy and waiting for next schedule.")
            last_heartbeat = time.time()
            
        time.sleep(10)


if __name__ == "__main__":
    main()