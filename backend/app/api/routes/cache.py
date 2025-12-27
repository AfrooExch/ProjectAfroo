"""
Cache Routes - Redis cache management (Admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user, require_admin
from app.services.cache_service import CacheService, clear_all_cache, invalidate_user_related_cache

router = APIRouter()


class InvalidateUserCacheRequest(BaseModel):
    """Request to invalidate user cache"""
    user_id: str


class InvalidateBalanceCacheRequest(BaseModel):
    """Request to invalidate balance cache"""
    user_id: str
    asset: str = None


@router.get("/admin/cache/stats", dependencies=[Depends(require_admin)])
async def get_cache_stats(current_user: dict = Depends(get_current_user)):
    """Get cache statistics and metrics"""
    try:
        stats = await CacheService.get_cache_stats()

        return {
            "success": True,
            "cache_stats": stats
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/cache/clear-all", dependencies=[Depends(require_admin)])
async def clear_all_cache_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Clear all application cache.
    USE WITH CAUTION - This will clear ALL cached data.
    """
    try:
        success = await clear_all_cache()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear cache"
            )

        return {
            "success": True,
            "message": "All cache cleared successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/cache/invalidate/user", dependencies=[Depends(require_admin)])
async def invalidate_user_cache(
    request: InvalidateUserCacheRequest,
    current_user: dict = Depends(get_current_user)
):
    """Invalidate all cache related to a specific user"""
    try:
        await invalidate_user_related_cache(request.user_id)

        return {
            "success": True,
            "message": f"Cache invalidated for user {request.user_id}"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/cache/invalidate/balance", dependencies=[Depends(require_admin)])
async def invalidate_balance_cache(
    request: InvalidateBalanceCacheRequest,
    current_user: dict = Depends(get_current_user)
):
    """Invalidate balance cache for user"""
    try:
        await CacheService.invalidate_balance_cache(
            user_id=request.user_id,
            asset=request.asset
        )

        return {
            "success": True,
            "message": f"Balance cache invalidated for user {request.user_id}"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/cache/invalidate/tos", dependencies=[Depends(require_admin)])
async def invalidate_tos_cache(current_user: dict = Depends(get_current_user)):
    """Invalidate all TOS cache"""
    try:
        await CacheService.invalidate_tos_cache()

        return {
            "success": True,
            "message": "TOS cache invalidated"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/cache/patterns", dependencies=[Depends(require_admin)])
async def list_cache_patterns(current_user: dict = Depends(get_current_user)):
    """List all cache key patterns used by the application"""
    try:
        patterns = {
            "user_data": f"{CacheService.PREFIX_USER}[user_id]",
            "balance": f"{CacheService.PREFIX_BALANCE}[user_id]:[asset]",
            "exchange_rate": f"{CacheService.PREFIX_EXCHANGE_RATE}[from]:[to]",
            "reputation": f"{CacheService.PREFIX_REPUTATION}[user_id]",
            "analytics": f"{CacheService.PREFIX_ANALYTICS}[metric]",
            "tos": f"{CacheService.PREFIX_TOS}[category]",
            "session": f"{CacheService.PREFIX_SESSION}[token]"
        }

        ttls = {
            "short": f"{CacheService.TTL_SHORT} seconds (5 minutes)",
            "medium": f"{CacheService.TTL_MEDIUM} seconds (30 minutes)",
            "long": f"{CacheService.TTL_LONG} seconds (1 hour)",
            "day": f"{CacheService.TTL_DAY} seconds (24 hours)"
        }

        return {
            "success": True,
            "patterns": patterns,
            "ttls": ttls
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
