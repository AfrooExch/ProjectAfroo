"""
Background Tasks - Scheduled jobs and periodic tasks
Uses APScheduler for running periodic balance syncs and other maintenance tasks
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from app.services.balance_sync_service import run_periodic_balance_sync
from app.services.afroo_swap_service import update_pending_swaps
from app.services.withdrawal_service import update_pending_withdrawals
from app.services.reputation_service import recalculate_all_stats
from app.services.ticket_service import TicketService
from app.services.profit_sweep_service import ProfitSweepService

logger = logging.getLogger(__name__)


async def run_mongodb_backup():
    """Run MongoDB LOCAL backup using backup script (4x daily)"""
    try:
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent / "scripts" / "backup_mongodb.py"

        logger.info("Starting MongoDB LOCAL backup...")

        # Run backup script (local only, no cloud)
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info("MongoDB LOCAL backup completed successfully")
            return True
        else:
            logger.error(f"MongoDB backup failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error running MongoDB backup: {e}", exc_info=True)
        return False


async def run_mongodb_cloud_backup():
    """
    Run MongoDB CLOUD backup to Atlas (1x daily at 4 AM)
    Uses MongoDB Atlas backup API to trigger backup and upload
    """
    try:
        import os
        import subprocess
        from pathlib import Path

        logger.info("Starting MongoDB CLOUD backup to Atlas...")

        # Check if cloud backup is configured
        mongodb_url = os.getenv("MONGODB_URL", "")

        # If using Atlas (mongodb+srv://), Atlas handles backups automatically via their service
        if "mongodb.net" in mongodb_url or "mongodb+srv://" in mongodb_url:
            logger.info("MongoDB Atlas detected - backups handled by Atlas Cloud Backup service")
            logger.info("Atlas automatic backup is enabled. No manual trigger needed.")
            logger.info("Configure backup policy at: https://cloud.mongodb.com/")
            return True

        # For self-hosted MongoDB, run backup script with cloud upload enabled
        script_path = Path(__file__).parent.parent.parent / "scripts" / "backup_mongodb.py"

        # Set environment variable to enable cloud upload
        env = os.environ.copy()
        env["BACKUP_CLOUD_ENABLED"] = "true"

        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=3600,
            env=env
        )

        if result.returncode == 0:
            logger.info("MongoDB CLOUD backup completed successfully")
            return True
        else:
            logger.error(f"MongoDB cloud backup failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error running MongoDB cloud backup: {e}", exc_info=True)
        return False


async def run_profit_sweep():
    """
    Run automated profit sweep.
    Sweeps accumulated fees from exchange and wallet operations to admin wallets.
    Runs twice daily at 6 AM and 6 PM.
    """
    try:
        logger.info("Starting automated profit sweep...")

        # Run sweep for all fees (exchange + wallet)
        result = await ProfitSweepService.sweep_all_fees(
            sweep_type="all",
            force=False,  # Respect minimum amounts
            dry_run=False
        )

        total_swept = result.get("total_swept_usd", 0.0)
        errors = result.get("errors", [])

        if errors:
            logger.warning(f"Profit sweep completed with errors: {errors}")
        else:
            logger.info(f"Profit sweep completed successfully: ${total_swept:.2f} USD")

        return result

    except Exception as e:
        logger.error(f"Error running profit sweep: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

# Global scheduler instance
scheduler = AsyncIOScheduler()


def start_background_tasks():
    """
    Start all background tasks.
    Called on application startup.
    """
    try:
        # Balance sync - every 30 minutes
        scheduler.add_job(
            run_periodic_balance_sync,
            trigger=IntervalTrigger(minutes=30),
            id="balance_sync",
            name="Periodic Balance Sync",
            replace_existing=True,
            max_instances=1  # Prevent overlapping runs
        )

        # Swap status updates - every 5 minutes
        scheduler.add_job(
            update_pending_swaps,
            trigger=IntervalTrigger(minutes=5),
            id="swap_status_update",
            name="Update Pending Swaps",
            replace_existing=True,
            max_instances=1
        )

        # Withdrawal status updates - every 5 minutes
        scheduler.add_job(
            update_pending_withdrawals,
            trigger=IntervalTrigger(minutes=5),
            id="withdrawal_status_update",
            name="Update Pending Withdrawals",
            replace_existing=True,
            max_instances=1
        )

        # Daily stats recalculation - 3 AM
        scheduler.add_job(
            recalculate_all_stats,
            trigger=CronTrigger(hour=3, minute=0),  # 3 AM daily
            id="recalculate_stats",
            name="Recalculate User Statistics",
            replace_existing=True
        )

        # Daily cleanup - Remove old sync records (keep 30 days)
        scheduler.add_job(
            cleanup_old_sync_records,
            trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
            id="cleanup_sync_records",
            name="Cleanup Old Sync Records",
            replace_existing=True
        )

        # TOS deadline monitoring - every 1 minute
        scheduler.add_job(
            TicketService.monitor_tos_deadlines,
            trigger=IntervalTrigger(minutes=1),
            id="tos_deadline_monitor",
            name="Monitor TOS Agreement Deadlines",
            replace_existing=True,
            max_instances=1
        )

        # Local MongoDB backup - every 6 hours (4x daily)
        scheduler.add_job(
            run_mongodb_backup,
            trigger=IntervalTrigger(hours=6),
            id="mongodb_backup_local",
            name="MongoDB Local Backup",
            replace_existing=True,
            max_instances=1
        )

        # Cloud MongoDB backup to Atlas - once daily at 4 AM
        scheduler.add_job(
            run_mongodb_cloud_backup,
            trigger=CronTrigger(hour=4, minute=0),
            id="mongodb_backup_cloud",
            name="MongoDB Cloud Backup",
            replace_existing=True,
            max_instances=1
        )

        # Profit sweep - twice daily (6 AM and 6 PM)
        scheduler.add_job(
            run_profit_sweep,
            trigger=CronTrigger(hour="6,18", minute=0),  # 6 AM and 6 PM
            id="profit_sweep",
            name="Profit Fee Sweep",
            replace_existing=True,
            max_instances=1
        )

        # Start scheduler
        scheduler.start()
        logger.info("Background tasks started successfully")
        logger.info("Scheduled jobs:")
        logger.info("  - Balance Sync: Every 30 minutes")
        logger.info("  - Swap Status Updates: Every 5 minutes")
        logger.info("  - Withdrawal Status Updates: Every 5 minutes")
        logger.info("  - Stats Recalculation: Daily at 3 AM")
        logger.info("  - Sync Record Cleanup: Daily at 2 AM")
        logger.info("  - TOS Deadline Monitor: Every 1 minute")
        logger.info("  - MongoDB Local Backup: Every 6 hours (4x daily)")
        logger.info("  - MongoDB Cloud Backup: Daily at 4 AM (Atlas)")
        logger.info("  - Profit Sweep: Twice daily at 6 AM and 6 PM")

    except Exception as e:
        logger.error(f"Failed to start background tasks: {e}", exc_info=True)


def stop_background_tasks():
    """
    Stop all background tasks.
    Called on application shutdown.
    """
    try:
        scheduler.shutdown(wait=True)
        logger.info("Background tasks stopped")
    except Exception as e:
        logger.error(f"Error stopping background tasks: {e}")


async def cleanup_old_sync_records():
    """
    Clean up old balance sync records (keep 30 days).
    Runs daily at 2 AM.
    """
    try:
        from datetime import timedelta
        from app.core.database import get_db_collection

        sync_db = await get_db_collection("balance_sync_records")

        # Delete records older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        result = await sync_db.delete_many({"synced_at": {"$lt": cutoff}})

        logger.info(f"Cleaned up {result.deleted_count} old sync records")

    except Exception as e:
        logger.error(f"Failed to cleanup old sync records: {e}", exc_info=True)


# Manual trigger functions (for admin endpoints)
async def trigger_balance_sync():
    """Manually trigger balance sync"""
    logger.info("Manual balance sync triggered")
    return await run_periodic_balance_sync()


async def trigger_profit_sweep(sweep_type: str = "all", force: bool = False):
    """
    Manually trigger profit sweep

    Args:
        sweep_type: "exchange", "wallet", or "all"
        force: Skip minimum amount checks
    """
    logger.info(f"Manual profit sweep triggered: type={sweep_type} force={force}")
    return await ProfitSweepService.sweep_all_fees(
        sweep_type=sweep_type,
        force=force,
        dry_run=False
    )


async def get_scheduler_status():
    """Get status of all scheduled jobs"""
    jobs = scheduler.get_jobs()

    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }
