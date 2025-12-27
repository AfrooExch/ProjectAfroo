"""
User Service - Business logic for user operations
Keeps routes clean, handles all user-related logic
"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from app.core.database import get_users_collection, get_audit_logs_collection
from app.models.user import User, UserCreate, UserUpdate


class UserService:
    """Service for user operations"""

    @staticmethod
    async def get_by_discord_id(discord_id: str) -> Optional[dict]:
        """Get user by Discord ID"""
        users = get_users_collection()
        return await users.find_one({"discord_id": discord_id})

    @staticmethod
    async def get_by_id(user_id: str) -> Optional[dict]:
        """Get user by MongoDB ID"""
        users = get_users_collection()
        return await users.find_one({"_id": ObjectId(user_id)})

    @staticmethod
    async def create_user(user_data: UserCreate) -> dict:
        """Create new user"""
        users = get_users_collection()

        # Check if user already exists
        existing = await users.find_one({"discord_id": user_data.discord_id})
        if existing:
            return existing

        # Create new user
        user_dict = {
            "discord_id": user_data.discord_id,
            "username": user_data.username,
            "discriminator": user_data.discriminator,
            "global_name": user_data.global_name,
            "avatar_hash": user_data.avatar_hash,
            "email": user_data.email,
            "status": "active",
            "kyc_level": 0,
            "reputation_score": 100,
            "roles": ["user"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await users.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id

        # Log user creation
        await UserService.log_action(
            str(result.inserted_id),
            "user.created",
            {"discord_id": user_data.discord_id}
        )

        return user_dict

    @staticmethod
    async def update_user(user_id: str, update_data: UserUpdate) -> Optional[dict]:
        """Update user"""
        users = get_users_collection()

        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()

        result = await users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_dict},
            return_document=True
        )

        if result:
            await UserService.log_action(
                user_id,
                "user.updated",
                {"fields": list(update_dict.keys())}
            )

        return result

    @staticmethod
    async def update_login_info(discord_id: str, ip_address: str, username: str = None, discriminator: str = None, global_name: str = None, avatar_hash: str = None):
        """Update user's last login information and Discord profile data"""
        users = get_users_collection()

        update_data = {
            "$set": {
                "last_login_at": datetime.utcnow(),
                "last_login_ip": ip_address,
                "updated_at": datetime.utcnow()
            },
            "$push": {
                "login_history": {
                    "$each": [{
                        "timestamp": datetime.utcnow(),
                        "ip_address": ip_address
                    }],
                    "$slice": -10  # Keep only last 10 logins
                }
            }
        }

        # Update Discord profile data if provided
        if username:
            update_data["$set"]["username"] = username
        if discriminator:
            update_data["$set"]["discriminator"] = discriminator
        if global_name is not None:  # Allow None to clear it
            update_data["$set"]["global_name"] = global_name
        if avatar_hash is not None:  # Allow None for users without custom avatar
            update_data["$set"]["avatar_hash"] = avatar_hash

        await users.update_one(
            {"discord_id": discord_id},
            update_data
        )

    @staticmethod
    async def suspend_user(user_id: str, reason: str, admin_id: str):
        """Suspend user account"""
        users = get_users_collection()

        result = await users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "status": "suspended",
                    "suspension_reason": reason,
                    "suspended_at": datetime.utcnow(),
                    "suspended_by": ObjectId(admin_id),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await UserService.log_action(
            user_id,
            "user.suspended",
            {"reason": reason, "admin_id": admin_id}
        )

        return result

    @staticmethod
    async def ban_user(user_id: str, reason: str, admin_id: str):
        """Ban user account permanently"""
        users = get_users_collection()

        result = await users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "status": "banned",
                    "ban_reason": reason,
                    "banned_at": datetime.utcnow(),
                    "banned_by": ObjectId(admin_id),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await UserService.log_action(
            user_id,
            "user.banned",
            {"reason": reason, "admin_id": admin_id}
        )

        return result

    @staticmethod
    async def log_action(user_id: str, action: str, details: dict):
        """Log user action to audit trail"""
        audit_logs = get_audit_logs_collection()

        await audit_logs.insert_one({
            "user_id": ObjectId(user_id),
            "actor_type": "system",
            "action": action,
            "resource_type": "user",
            "resource_id": ObjectId(user_id),
            "details": details,
            "created_at": datetime.utcnow()
        })

    # ====================
    # Discord Integration
    # ====================

    @staticmethod
    async def create_from_discord(
        discord_id: str,
        username: str,
        discriminator: str,
        global_name: str = None,
        avatar_hash: str = None
    ) -> dict:
        """Create user from Discord data"""
        users = get_users_collection()

        # Check if user already exists
        existing = await users.find_one({"discord_id": discord_id})
        if existing:
            return existing

        # Create new user
        user_dict = {
            "discord_id": discord_id,
            "username": username,
            "discriminator": discriminator,
            "global_name": global_name,
            "avatar_hash": avatar_hash,
            "status": "active",
            "kyc_level": 0,
            "reputation_score": 100,
            "roles": ["user"],
            "discord_roles": [],  # Discord role IDs
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await users.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id

        await UserService.log_action(
            str(result.inserted_id),
            "user.created_from_discord",
            {"discord_id": discord_id}
        )

        return user_dict

    @staticmethod
    async def sync_discord_roles(discord_id: str, role_ids: List[int]) -> dict:
        """
        Sync Discord roles to database
        Called by bot when user interacts or roles change
        """
        users = get_users_collection()

        result = await users.find_one_and_update(
            {"discord_id": discord_id},
            {
                "$set": {
                    "discord_roles": role_ids,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        return result

    @staticmethod
    async def update_discord_info(
        discord_id: str,
        username: str = None,
        discriminator: str = None,
        global_name: str = None,
        avatar_hash: str = None
    ):
        """Update user's Discord information"""
        users = get_users_collection()

        update_data = {
            "updated_at": datetime.utcnow()
        }

        if username:
            update_data["username"] = username
        if discriminator:
            update_data["discriminator"] = discriminator
        if global_name:
            update_data["global_name"] = global_name
        if avatar_hash:
            update_data["avatar_hash"] = avatar_hash

        await users.update_one(
            {"discord_id": discord_id},
            {"$set": update_data}
        )

    # ====================
    # Permission Checks
    # ====================

    @staticmethod
    async def is_admin(discord_id: str) -> bool:
        """Check if user has admin role"""
        from app.core.config import settings

        user = await UserService.get_by_discord_id(discord_id)
        if not user:
            return False

        discord_roles = user.get("discord_roles", [])

        # Check if user has head admin role
        admin_role_id = settings.ROLE_HEAD_ADMIN
        if admin_role_id and admin_role_id in discord_roles:
            return True

        return False

    @staticmethod
    async def is_admin(discord_id: str) -> bool:
        """Check if user is admin (Head Admin or Assistant Admin)"""
        from app.core.config import settings

        user = await UserService.get_by_discord_id(discord_id)
        if not user:
            return False

        discord_roles = user.get("discord_roles", [])

        # Check for Head Admin or Assistant Admin role
        head_admin_role_id = settings.ROLE_HEAD_ADMIN
        assistant_admin_role_id = settings.ROLE_ASSISTANT_ADMIN

        if head_admin_role_id and head_admin_role_id in discord_roles:
            return True

        if assistant_admin_role_id and assistant_admin_role_id in discord_roles:
            return True

        return False

    @staticmethod
    async def is_staff(discord_id: str) -> bool:
        """Check if user is staff (staff or admin)"""
        from app.core.config import settings

        user = await UserService.get_by_discord_id(discord_id)
        if not user:
            return False

        discord_roles = user.get("discord_roles", [])

        # Check for staff or admin role
        staff_role_id = settings.ROLE_STAFF
        admin_role_id = settings.ROLE_HEAD_ADMIN

        if staff_role_id and staff_role_id in discord_roles:
            return True

        if admin_role_id and admin_role_id in discord_roles:
            return True

        return False

    @staticmethod
    async def is_exchanger(discord_id: str) -> bool:
        """Check if user is exchanger"""
        from app.core.config import settings

        user = await UserService.get_by_discord_id(discord_id)
        if not user:
            return False

        discord_roles = user.get("discord_roles", [])

        # Check for exchanger role
        exchanger_role_id = settings.ROLE_EXCHANGER
        if exchanger_role_id and exchanger_role_id in discord_roles:
            return True

        return False

    @staticmethod
    async def can_access_resource(
        discord_id: str,
        resource_type: str,
        resource_owner_id: str
    ) -> bool:
        """
        Check if user can access a resource

        Args:
            discord_id: User's Discord ID
            resource_type: Type of resource (wallet, ticket, etc.)
            resource_owner_id: Discord ID of resource owner

        Returns:
            True if user can access, False otherwise
        """
        # Admins can access anything
        if await UserService.is_admin(discord_id):
            return True

        # Staff can access most things
        if resource_type in ["ticket", "support_ticket"] and await UserService.is_staff(discord_id):
            return True

        # Users can access their own resources
        if discord_id == resource_owner_id:
            return True

        return False


# Singleton instance
user_service = UserService()
