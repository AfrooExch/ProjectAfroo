"""
Analytics Routes - Platform statistics and insights (Admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime, timedelta

from app.api.dependencies import get_current_user, require_admin
from app.services.analytics_service import AnalyticsService, get_cached_platform_overview

router = APIRouter()


@router.get("/admin/analytics/overview", dependencies=[Depends(require_admin)])
async def get_platform_overview(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """
    Get platform overview statistics.
    Cached for 5 minutes for performance.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Use cached version if days=30
        if days == 30:
            overview = await get_cached_platform_overview()
        else:
            overview = await AnalyticsService.get_platform_overview(
                start_date=start_date,
                end_date=end_date
            )

        return {
            "success": True,
            "overview": overview
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/analytics/revenue", dependencies=[Depends(require_admin)])
async def get_revenue_stats(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get platform revenue statistics"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        revenue = await AnalyticsService.get_revenue_stats(
            start_date=start_date,
            end_date=end_date
        )

        return {
            "success": True,
            "revenue": revenue
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/analytics/asset-distribution", dependencies=[Depends(require_admin)])
async def get_asset_distribution(current_user: dict = Depends(get_current_user)):
    """Get asset distribution across platform"""
    try:
        distribution = await AnalyticsService.get_asset_distribution()

        return {
            "success": True,
            "distribution": distribution
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/analytics/user/{user_id}", dependencies=[Depends(require_admin)])
async def get_user_analytics(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed analytics for specific user"""
    try:
        analytics = await AnalyticsService.get_user_analytics(user_id)

        return {
            "success": True,
            "user_analytics": analytics
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/analytics/time-series", dependencies=[Depends(require_admin)])
async def get_time_series_data(
    metric: str,
    days: int = 30,
    interval: str = "daily",
    current_user: dict = Depends(get_current_user)
):
    """
    Get time series data for metric.

    Metrics: tickets, revenue
    Intervals: daily, weekly, monthly
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        time_series = await AnalyticsService.get_time_series_data(
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            interval=interval
        )

        return {
            "success": True,
            "metric": metric,
            "interval": interval,
            "data": time_series
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/analytics/exchanger-rankings", dependencies=[Depends(require_admin)])
async def get_exchanger_rankings(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get top exchangers by various metrics"""
    try:
        rankings = await AnalyticsService.get_exchanger_rankings(limit=limit)

        return {
            "success": True,
            "rankings": rankings
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
