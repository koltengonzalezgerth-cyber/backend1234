"""
Runs the ingestion cycle on a recurring interval inside the same process
as the API server. For higher-traffic production use, run this as a
separate worker process/cron job instead of inside the API process.
"""
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.ingestion.run_ingest import run_ingest_cycle

scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(
        run_ingest_cycle,
        "interval",
        minutes=settings.INGEST_INTERVAL_MINUTES,
        next_run_time=datetime.now(),  # run once immediately on boot (fast feedback
                                        # when testing), then every INGEST_INTERVAL_MINUTES
                                        # after that via the interval trigger. IMPORTANT:
                                        # passing None here (instead of omitting this
                                        # argument or giving it a real datetime) tells
                                        # APScheduler to add the job PAUSED — it would
                                        # never run automatically at all. Don't remove
                                        # this line without replacing it with a real value.
        id="ingest_cycle",
        replace_existing=True,
        max_instances=1,       # never run two ingestion cycles concurrently
        coalesce=True,         # if a run was missed (e.g. process was asleep), run once, not N times
        misfire_grace_time=120,
    )
    scheduler.start()
