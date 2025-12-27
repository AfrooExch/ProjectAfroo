"""
Admin Scheduler Routes
Endpoints for managing background tasks and scheduler
"""

from fastapi import APIRouter, HTTPException, Depends
import logging

from app.api.dependencies import require_admin
from app.tasks import get_scheduler_status
from app.tasks.ticket_cleanup import run_cleanup_task

router = APIRouter(prefix="/api/v1/admin/scheduler", tags=["Admin - Scheduler"])

logger = logging.getLogger(__name__)


@router.get("/status")
async def get_status(admin=Depends(require_admin)):
    """
    Get scheduler status and list of scheduled jobs.

    **Admin only**

    Returns:
        - running: Whether scheduler is running
        - jobs: List of scheduled jobs with next run times
    """
    try:
        status = get_scheduler_status()
        return {
            "success": True,
            "scheduler": status
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduler status: {str(e)}"
        )


@router.post("/cleanup/run-now")
async def run_cleanup_now(admin=Depends(require_admin)):
    """
    Manually trigger the ticket cleanup task (auto-close old unclaimed tickets).

    **Admin only**

    This runs the same task that runs hourly via the scheduler,
    but can be triggered manually for testing or immediate cleanup.

    Returns:
        - closed_count: Number of tickets closed
        - tickets_closed: List of closed tickets with details
    """
    try:
        logger.info(f"Admin {admin.get('discord_id', 'unknown')} manually triggered cleanup task")

        result = await run_cleanup_task()

        return {
            "success": result["success"],
            "closed_count": result["closed_count"],
            "tickets_closed": result.get("tickets_closed", []),
            "message": f"Cleanup completed: {result['closed_count']} tickets closed"
        }

    except Exception as e:
        logger.error(f"Error running manual cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run cleanup: {str(e)}"
        )
