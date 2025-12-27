"""
Reputation Routes - User ratings, reviews, and leaderboards
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.api.dependencies import get_current_user
from app.services.reputation_service import ReputationService

router = APIRouter()


class SubmitRatingRequest(BaseModel):
    """Request to submit a rating"""
    ticket_id: str
    rated_user_id: str
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    rater_role: str = Field(..., pattern="^(client|exchanger)$")


@router.post("/reputation/rate")
async def submit_rating(
    request: SubmitRatingRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit rating for completed ticket"""
    try:
        success, message = await ReputationService.submit_rating(
            ticket_id=request.ticket_id,
            rater_id=str(current_user["_id"]),
            rated_id=request.rated_user_id,
            rating=request.rating,
            review=request.review,
            rater_role=request.rater_role
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


@router.get("/reputation/user/{user_id}")
async def get_user_reputation(user_id: str):
    """Get user's reputation summary (public)"""
    try:
        reputation = await ReputationService.get_user_reputation(user_id)

        return {
            "success": True,
            "reputation": reputation
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reputation/stats/{user_id}")
async def get_user_statistics(user_id: str):
    """Get user's activity statistics"""
    try:
        stats = await ReputationService.get_user_statistics(user_id)

        return {
            "success": True,
            "statistics": stats
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reputation/trust-score/{user_id}")
async def get_trust_score(user_id: str):
    """Get user's trust score (0-100 with breakdown)"""
    try:
        trust_score = await ReputationService.get_trust_score(user_id)

        return {
            "success": True,
            "trust_score": trust_score
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reputation/leaderboard/{category}")
async def get_leaderboard(
    category: str,
    time_period: str = "all_time",
    limit: int = 50
):
    """
    Get leaderboard for category.

    Categories: top_exchangers, top_clients, most_active, highest_volume
    Time periods: all_time, monthly, weekly
    """
    try:
        leaderboard = await ReputationService.get_leaderboard(
            category=category,
            time_period=time_period,
            limit=limit
        )

        return {
            "success": True,
            "category": category,
            "time_period": time_period,
            "leaderboard": leaderboard
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reputation/my-reputation")
async def get_my_reputation(current_user: dict = Depends(get_current_user)):
    """Get current user's reputation"""
    try:
        reputation = await ReputationService.get_user_reputation(
            str(current_user["_id"])
        )
        stats = await ReputationService.get_user_statistics(
            str(current_user["_id"])
        )
        trust_score = await ReputationService.get_trust_score(
            str(current_user["_id"])
        )

        return {
            "success": True,
            "reputation": reputation,
            "statistics": stats,
            "trust_score": trust_score
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
