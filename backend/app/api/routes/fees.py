"""
Fee Collection API Routes
Admin endpoints for platform fee management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.services.fee_collection_service import FeeCollectionService
from app.api.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("/summary")
async def get_fee_summary(
    asset: Optional[str] = Query(None, description="Filter by asset"),
    collected: Optional[bool] = Query(None, description="Filter by collection status"),
    current_user: dict = Depends(require_admin)
):
    """
    Get fee collection summary.
    Admin only.
    """
    try:
        summary = await FeeCollectionService.get_fee_summary(
            asset=asset,
            collected=collected
        )

        return {
            "success": True,
            "summary": summary
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fee summary: {str(e)}"
        )


@router.get("/uncollected")
async def get_uncollected_fees(
    asset: Optional[str] = Query(None, description="Filter by asset"),
    current_user: dict = Depends(require_admin)
):
    """
    Get uncollected fees ready for admin withdrawal.
    Admin only.
    """
    try:
        fees = await FeeCollectionService.get_uncollected_fees(asset=asset)

        # Serialize ObjectId fields
        for fee in fees:
            fee["_id"] = str(fee["_id"])
            fee["transaction_id"] = str(fee["transaction_id"])
            fee["user_id"] = str(fee["user_id"])

        # Calculate totals
        total_by_asset = {}
        for fee in fees:
            asset_key = fee["asset"]
            if asset_key not in total_by_asset:
                total_by_asset[asset_key] = {
                    "asset": asset_key,
                    "total_units": 0.0,
                    "total_usd": 0.0,
                    "count": 0
                }
            total_by_asset[asset_key]["total_units"] += fee["amount_units"]
            total_by_asset[asset_key]["total_usd"] += fee["amount_usd"]
            total_by_asset[asset_key]["count"] += 1

        return {
            "success": True,
            "fees": fees,
            "count": len(fees),
            "totals": list(total_by_asset.values())
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get uncollected fees: {str(e)}"
        )


@router.post("/collect")
async def mark_fees_collected(
    fee_ids: list[str],
    tx_hash: str,
    current_user: dict = Depends(require_admin)
):
    """
    Mark fees as collected after admin withdrawal.
    Admin only.
    """
    try:
        if not fee_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fee_ids cannot be empty"
            )

        if not tx_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tx_hash is required"
            )

        modified_count = await FeeCollectionService.mark_fees_collected(
            fee_ids=fee_ids,
            tx_hash=tx_hash
        )

        return {
            "success": True,
            "message": f"Marked {modified_count} fees as collected",
            "modified_count": modified_count,
            "tx_hash": tx_hash
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark fees as collected: {str(e)}"
        )


@router.get("/monthly/{month}")
async def get_monthly_report(
    month: str,
    current_user: dict = Depends(require_admin)
):
    """
    Get fee report for specific month (format: YYYY-MM).
    Admin only.
    """
    try:
        # Validate month format
        if len(month) != 7 or month[4] != "-":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month must be in format YYYY-MM"
            )

        report = await FeeCollectionService.get_monthly_report(month)

        return {
            "success": True,
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monthly report: {str(e)}"
        )
