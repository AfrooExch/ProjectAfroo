"""
Partner Routes - Partner program management
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.api.dependencies import get_current_active_user, require_admin
from app.services.partner_service import PartnerService
from app.models.partner import PartnerCreate

router = APIRouter(tags=["Partners"])


@router.get("/me")
async def get_my_partner_info(
    user: dict = Depends(get_current_active_user)
):
    """Get current user's partner info"""

    if "partner" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Not a partner")

    user_id = str(user["_id"])
    partner = await PartnerService.get_partner_by_user_id(user_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Hide sensitive API key (show partial)
    api_key = partner["api_key"]
    masked_key = f"{api_key[:10]}...{api_key[-4:]}"

    return {
        "id": str(partner["_id"]),
        "name": partner["name"],
        "slug": partner["slug"],
        "tier": partner["tier"],
        "api_key": masked_key,
        "status": partner["status"],
        "total_volume": partner.get("total_volume", 0.0),
        "total_revenue": partner.get("total_revenue", 0.0),
        "total_exchanges": partner.get("total_exchanges", 0),
        "created_at": partner["created_at"]
    }


@router.post("/regenerate-api-key")
async def regenerate_api_key(
    user: dict = Depends(get_current_active_user)
):
    """Regenerate partner API key"""

    if "partner" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Not a partner")

    user_id = str(user["_id"])
    partner = await PartnerService.get_partner_by_user_id(user_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    new_api_key = await PartnerService.regenerate_api_key(str(partner["_id"]))

    return {
        "message": "API key regenerated successfully",
        "api_key": new_api_key
    }


@router.get("/stats")
async def get_partner_stats(
    user: dict = Depends(get_current_active_user)
):
    """Get partner statistics"""

    if "partner" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Not a partner")

    user_id = str(user["_id"])
    partner = await PartnerService.get_partner_by_user_id(user_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    return {
        "total_volume": partner.get("total_volume", 0.0),
        "total_revenue": partner.get("total_revenue", 0.0),
        "total_exchanges": partner.get("total_exchanges", 0),
        "tier": partner["tier"],
        "status": partner["status"]
    }


# Admin endpoints
@router.post("/admin/create")
async def create_partner(
    partner_data: PartnerCreate,
    admin: dict = Depends(require_admin)
):
    """Create new partner (admin only)"""

    admin_id = str(admin["_id"])

    try:
        partner = await PartnerService.create_partner(admin_id, partner_data)

        return {
            "message": "Partner created successfully",
            "partner": {
                "id": str(partner["_id"]),
                "name": partner["name"],
                "slug": partner["slug"],
                "tier": partner["tier"],
                "api_key": partner["api_key"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/list")
async def list_partners(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    admin: dict = Depends(require_admin)
):
    """List all partners (admin only)"""

    partners = await PartnerService.list_partners(status=status, tier=tier, limit=limit)

    return {
        "partners": [
            {
                "id": str(p["_id"]),
                "name": p["name"],
                "slug": p["slug"],
                "tier": p["tier"],
                "status": p["status"],
                "total_volume": p.get("total_volume", 0.0),
                "total_revenue": p.get("total_revenue", 0.0),
                "total_exchanges": p.get("total_exchanges", 0),
                "created_at": p["created_at"]
            }
            for p in partners
        ],
        "count": len(partners)
    }


@router.post("/admin/{partner_id}/suspend")
async def suspend_partner(
    partner_id: str,
    reason: str,
    admin: dict = Depends(require_admin)
):
    """Suspend partner (admin only)"""

    admin_id = str(admin["_id"])
    result = await PartnerService.suspend_partner(partner_id, reason, admin_id)

    if not result:
        raise HTTPException(status_code=404, detail="Partner not found")

    return {
        "message": "Partner suspended successfully",
        "partner_id": partner_id
    }
