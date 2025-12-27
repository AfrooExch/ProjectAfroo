"""
Background Task Scheduler
Sets up APScheduler to run periodic background tasks
"""

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns:
        AsyncIOScheduler: Configured scheduler instance
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already exists, returning existing instance")
        return scheduler

    scheduler = AsyncIOScheduler()

    # Configure timezone
    scheduler.configure(timezone="UTC")

    logger.info("Scheduler created successfully")
    return scheduler


def start_scheduler():
    """
    Start the scheduler and register all background tasks.
    """
    global scheduler

    if scheduler is None:
        scheduler = create_scheduler()

    # Import task functions
    from app.tasks.ticket_cleanup import run_cleanup_task

    # Add ticket auto-close task (runs every hour)
    scheduler.add_job(
        run_cleanup_task,
        trigger=IntervalTrigger(hours=1),
        id="ticket_auto_close",
        name="Auto-close unclaimed tickets older than 12 hours",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
        next_run_time=datetime.utcnow()  # Run immediately on startup
    )

    # Start the scheduler
    scheduler.start()

    logger.info("Scheduler started with registered tasks:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {job.next_run_time}")


def stop_scheduler():
    """
    Stop the scheduler gracefully.
    """
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")
        scheduler = None
    else:
        logger.warning("Scheduler is not running")


def get_scheduler_status() -> dict:
    """
    Get the current status of the scheduler.

    Returns:
        dict: Scheduler status including running state and active jobs
    """
    global scheduler

    if scheduler is None:
        return {
            "running": False,
            "jobs": []
        }

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
        "job_count": len(jobs)
    }
