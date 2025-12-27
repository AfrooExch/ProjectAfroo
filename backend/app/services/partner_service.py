"""
Partner Service - Business logic for partner program operations
"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import secrets

from app.core.database import (
    get_partners_collection,
    get_users_collection,
    get_audit_logs_collection
)
from app.models.partner import Partner, PartnerCreate


class PartnerService:
    """Service for partner operations"""

    @staticmethod
    async def create_partner(admin_id: str, partner_data: PartnerCreate) -> dict:
        """Create new partner"""
        partners = get_partners_collection()

        # Generate API key
        api_key = f"afroo_{secrets.token_urlsafe(32)}"

        # Note: Using newer V4 partner schema
        partner_dict = {
            "name": partner_data.name,
            "slug": partner_data.slug,
            "discord_guild_id": partner_data.discord_guild_id,
            "discord_owner_id": partner_data.discord_owner_id,
            "api_key": api_key,
            "branding": {},
            "config": {},
            "fee_structure": {
                "platform_fee_percent": 1.0,
                "partner_fee_percent": 0.5,
                "exchanger_fee_percent": 1.0,
                "revenue_share_percent": 20.0
            },
            "max_exchangers": 10,
            "max_monthly_volume": None,
            "status": "active",
            "tier": "basic",
            "total_exchanges": 0,
            "total_volume": 0.0,
            "total_revenue": 0.0,
            "created_at": datetime.utcnow(),
            "activated_at": None,
            "expires_at": None,
            "updated_at": datetime.utcnow()
        }

        result = await partners.insert_one(partner_dict)
        partner_dict["_id"] = result.inserted_id

        # Add partner role to user
        users = get_users_collection()
        await users.update_one(
            {"_id": ObjectId(partner_data.user_id)},
            {"$addToSet": {"roles": "partner"}}
        )

        await PartnerService.log_action(
            str(result.inserted_id),
            admin_id,
            "partner.created",
            {"name": partner_data.name, "tier": "basic"}
        )

        return partner_dict

    @staticmethod
    async def get_partner_by_user_id(user_id: str) -> Optional[dict]:
        """Get partner by user ID"""
        partners = get_partners_collection()
        return await partners.find_one({"user_id": ObjectId(user_id)})

    @staticmethod
    async def get_partner_by_api_key(api_key: str) -> Optional[dict]:
        """Get partner by API key"""
        partners = get_partners_collection()
        return await partners.find_one({"api_key": api_key, "api_enabled": True})

    @staticmethod
    async def regenerate_api_key(partner_id: str) -> str:
        """Regenerate partner API key"""
        partners = get_partners_collection()

        new_api_key = f"afroo_{secrets.token_urlsafe(32)}"

        await partners.update_one(
            {"_id": ObjectId(partner_id)},
            {
                "$set": {
                    "api_key": new_api_key,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return new_api_key

    @staticmethod
    async def update_partner_stats(partner_id: str, volume: float, commission: float):
        """Update partner statistics"""
        partners = get_partners_collection()

        await partners.update_one(
            {"_id": ObjectId(partner_id)},
            {
                "$inc": {
                    "total_volume": volume,
                    "total_commission": commission
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

    @staticmethod
    async def add_referred_user(partner_id: str, user_id: str):
        """Add user to partner's referral list"""
        partners = get_partners_collection()

        await partners.update_one(
            {"_id": ObjectId(partner_id)},
            {
                "$addToSet": {"referred_users": ObjectId(user_id)},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

    @staticmethod
    async def list_partners(
        status: Optional[str] = None,
        tier: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """List partners with filters"""
        partners = get_partners_collection()

        query = {}
        if status:
            query["status"] = status
        if tier:
            query["tier"] = tier

        cursor = partners.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    async def suspend_partner(partner_id: str, reason: str, admin_id: str):
        """Suspend partner"""
        partners = get_partners_collection()

        result = await partners.find_one_and_update(
            {"_id": ObjectId(partner_id)},
            {
                "$set": {
                    "status": "suspended",
                    "suspension_reason": reason,
                    "suspended_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await PartnerService.log_action(
            partner_id,
            admin_id,
            "partner.suspended",
            {"reason": reason}
        )

        return result

    @staticmethod
    async def log_action(partner_id: str, user_id: str, action: str, details: dict):
        """Log partner action"""
        audit_logs = get_audit_logs_collection()

        await audit_logs.insert_one({
            "user_id": ObjectId(user_id),
            "actor_type": "admin",
            "action": action,
            "resource_type": "partner",
            "resource_id": ObjectId(partner_id),
            "details": details,
            "created_at": datetime.utcnow()
        })
