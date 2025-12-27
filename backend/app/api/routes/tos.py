"""
TOS Routes - Terms of Service management and acceptance
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.api.dependencies import get_current_user, require_admin
from app.services.tos_service import TOSService

router = APIRouter()


class TOSCreateRequest(BaseModel):
    """Request to create new TOS version"""
    category: str
    version: str
    content: str
    summary: Optional[str] = None
    effective_date: Optional[datetime] = None


class TOSAgreementRequest(BaseModel):
    """Request to record TOS agreement"""
    tos_id: str


@router.get("/tos/latest/{category}")
async def get_latest_tos(category: str = "general"):
    """Get latest active TOS version for category (public)"""
    try:
        tos = await TOSService.get_latest_tos(category)

        if not tos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No TOS found for category: {category}"
            )

        return {
            "success": True,
            "tos": tos
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tos/all-active")
async def get_all_active_tos():
    """Get all active TOS versions (one per category) (public)"""
    try:
        all_tos = await TOSService.get_all_active_tos()

        return {
            "success": True,
            "tos_versions": all_tos,
            "categories": list(all_tos.keys())
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tos/history/{category}")
async def get_tos_history(category: str):
    """Get all TOS versions for category (public)"""
    try:
        history = await TOSService.get_tos_history(category)

        return {
            "success": True,
            "category": category,
            "versions": history
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/tos/agree")
async def record_tos_agreement(
    request: TOSAgreementRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Record user agreement to specific TOS version"""
    try:
        # Get IP and user agent
        ip_address = http_request.client.host
        user_agent = http_request.headers.get("user-agent", "")

        success, message = await TOSService.record_agreement(
            user_id=str(current_user["_id"]),
            tos_id=request.tos_id,
            ip_address=ip_address,
            user_agent=user_agent
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


@router.post("/tos/agree-all")
async def record_all_agreements(
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Record user agreement to all active TOS versions"""
    try:
        ip_address = http_request.client.host
        user_agent = http_request.headers.get("user-agent", "")

        success, message = await TOSService.record_all_agreements(
            user_id=str(current_user["_id"]),
            ip_address=ip_address,
            user_agent=user_agent
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


@router.get("/tos/check-compliance")
async def check_tos_compliance(current_user: dict = Depends(get_current_user)):
    """Check if user has agreed to all latest TOS versions"""
    try:
        agreements = await TOSService.has_agreed_to_all_latest(
            str(current_user["_id"])
        )

        all_agreed = all(agreements.values())

        return {
            "success": True,
            "compliant": all_agreed,
            "agreements": agreements
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tos/require-acceptance")
async def require_tos_acceptance(current_user: dict = Depends(get_current_user)):
    """Get list of TOS versions that user needs to accept"""
    try:
        required = await TOSService.require_tos_acceptance(
            str(current_user["_id"])
        )

        return {
            "success": True,
            **required
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tos/my-agreements")
async def get_my_agreements(current_user: dict = Depends(get_current_user)):
    """Get user's TOS agreement history"""
    try:
        agreements = await TOSService.get_user_agreements(
            str(current_user["_id"])
        )

        return {
            "success": True,
            "agreements": agreements
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Admin endpoints
@router.post("/admin/tos/create", dependencies=[Depends(require_admin)])
async def create_tos_version(
    request: TOSCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create new TOS version (admin only)"""
    try:
        success, message, tos_id = await TOSService.create_tos_version(
            category=request.category,
            version=request.version,
            content=request.content,
            summary=request.summary,
            effective_date=request.effective_date
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "tos_id": tos_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/tos/stats/{tos_id}", dependencies=[Depends(require_admin)])
async def get_tos_stats(
    tos_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get agreement statistics for TOS version (admin only)"""
    try:
        stats = await TOSService.get_agreement_stats(tos_id)

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
