"""
Exchanger Application Routes - API endpoints for exchanger applications
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.api.dependencies import get_current_user, require_admin, get_user_from_bot_request
from app.services.exchanger_application_service import ExchangerApplicationService

router = APIRouter()


class ApplicationSubmitRequest(BaseModel):
    """Request to submit exchanger application"""
    payment_methods: str = Field(..., min_length=10, max_length=500)
    crypto_holdings: str = Field(..., min_length=5, max_length=200)
    experience: str = Field(..., min_length=20, max_length=1000)
    availability: str = Field(..., min_length=10, max_length=200)


class ApplicationReviewRequest(BaseModel):
    """Request to review exchanger application"""
    status: str = Field(..., pattern="^(under_review|approved|rejected)$")
    review_notes: Optional[str] = None


@router.post("/exchanger-applications/submit")
async def submit_application(
    request: ApplicationSubmitRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Submit exchanger application via Discord bot.
    User must not already be an exchanger or have a pending application.
    """
    try:
        success, message, application_id = await ExchangerApplicationService.create_application(
            user_id=discord_user_id,
            payment_methods=request.payment_methods,
            crypto_holdings=request.crypto_holdings,
            experience=request.experience,
            availability=request.availability,
            discord_username=f"Discord-{discord_user_id}"
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "application_id": application_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/exchanger-applications/my-applications")
async def get_my_applications(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's application history"""
    try:
        applications = await ExchangerApplicationService.get_user_applications(
            str(current_user["_id"])
        )

        return {
            "success": True,
            "applications": applications
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/exchanger-applications/{application_id}")
async def get_application(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get application details.
    User can only view their own applications unless they are staff.
    """
    try:
        application = await ExchangerApplicationService.get_application(application_id)

        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Check ownership unless staff
        is_staff = any(role in current_user.get("roles", []) for role in ["admin", "mod", "staff"])
        if not is_staff and str(application["user_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this application"
            )

        return {
            "success": True,
            "application": application
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/exchanger-applications/pending", dependencies=[Depends(require_admin)])
async def get_pending_applications(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all pending applications (admin only)"""
    try:
        applications = await ExchangerApplicationService.get_pending_applications(limit)

        return {
            "success": True,
            "applications": applications,
            "count": len(applications)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/exchanger-applications/{application_id}/review")
async def review_application(
    application_id: str,
    request: ApplicationReviewRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Review exchanger application via Discord bot (admin only).

    Status options:
    - under_review: Mark as under review
    - approved: Approve and grant exchanger role
    - rejected: Reject application
    """
    try:
        success, message = await ExchangerApplicationService.update_application_status(
            application_id=application_id,
            status=request.status,
            reviewed_by=discord_user_id,
            review_notes=request.review_notes
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/admin/exchanger-applications/{application_id}", dependencies=[Depends(require_admin)])
async def delete_application(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete application (admin only)"""
    try:
        success, message = await ExchangerApplicationService.delete_application(application_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/exchanger-applications/stats", dependencies=[Depends(require_admin)])
async def get_application_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get application statistics (admin only)"""
    try:
        stats = await ExchangerApplicationService.get_application_stats()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/admin/exchanger-applications/user/{user_id}/clear")
async def clear_user_applications(
    user_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Clear all pending applications for a user (bot-authenticated admin only)"""
    try:
        from app.core.database import get_database
        db = get_database()

        # Delete all pending/under_review applications for this user
        result = await db.exchanger_applications.delete_many({
            "user_id": user_id,
            "status": {"$in": ["pending", "under_review"]}
        })

        return {
            "success": True,
            "message": f"Cleared {result.deleted_count} pending application(s)",
            "count": result.deleted_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
