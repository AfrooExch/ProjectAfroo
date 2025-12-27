"""
Exchanger Application Service - Handle applications to become an exchanger

Provides functionality for users to apply to become exchangers and for admins to review/approve applications.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List
from bson import ObjectId

from app.core.database import get_database

logger = logging.getLogger(__name__)


class ExchangerApplicationService:
    """Service for managing exchanger applications"""

    @staticmethod
    async def create_application(
        user_id: str,
        payment_methods: str,
        crypto_holdings: str,
        experience: str,
        availability: str,
        discord_username: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Create a new exchanger application.

        Args:
            user_id: User's ID
            payment_methods: Payment methods the applicant has
            crypto_holdings: Crypto holdings description
            experience: Trading experience and vouches
            availability: Timezone and availability
            discord_username: Discord username

        Returns:
            Tuple of (success, message, application_id)
        """
        try:
            db = get_database()

            # Check for existing pending applications
            existing = await db.exchanger_applications.find_one({
                "user_id": user_id,
                "status": {"$in": ["pending", "under_review"]}
            })

            if existing:
                return False, "You already have a pending application. Please wait for review.", None

            # Check if user is already an exchanger
            from app.core.database import get_users_collection
            users = get_users_collection()
            user = await users.find_one({"user_id": user_id})

            if user and "exchanger" in user.get("roles", []):
                return False, "You are already an exchanger.", None

            # Create application
            application = {
                "user_id": user_id,
                "discord_username": discord_username,
                "payment_methods": payment_methods,
                "crypto_holdings": crypto_holdings,
                "experience": experience,
                "availability": availability,
                "status": "pending",  # pending, under_review, approved, rejected
                "submitted_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "reviewed_by": None,
                "reviewed_at": None,
                "review_notes": None
            }

            result = await db.exchanger_applications.insert_one(application)
            application_id = str(result.inserted_id)

            logger.info(f"Created exchanger application {application_id} for user {user_id}")

            return True, "Application submitted successfully", application_id

        except Exception as e:
            logger.error(f"Failed to create exchanger application: {e}")
            return False, f"Failed to submit application: {str(e)}", None

    @staticmethod
    async def get_application(application_id: str) -> Optional[Dict]:
        """
        Get application by ID.

        Args:
            application_id: Application ID

        Returns:
            Application document or None
        """
        try:
            db = get_database()
            application = await db.exchanger_applications.find_one({
                "_id": ObjectId(application_id)
            })

            if application:
                application["_id"] = str(application["_id"])

            return application

        except Exception as e:
            logger.error(f"Failed to get application {application_id}: {e}")
            return None

    @staticmethod
    async def get_user_applications(user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get user's applications.

        Args:
            user_id: User ID
            limit: Maximum number of results

        Returns:
            List of applications
        """
        try:
            db = get_database()
            cursor = db.exchanger_applications.find(
                {"user_id": user_id}
            ).sort("submitted_at", -1).limit(limit)

            applications = await cursor.to_list(length=limit)

            # Convert ObjectId to string
            for app in applications:
                app["_id"] = str(app["_id"])

            return applications

        except Exception as e:
            logger.error(f"Failed to get user applications for {user_id}: {e}")
            return []

    @staticmethod
    async def get_pending_applications(limit: int = 50) -> List[Dict]:
        """
        Get all pending applications (admin).

        Args:
            limit: Maximum number of results

        Returns:
            List of pending applications
        """
        try:
            db = get_database()
            cursor = db.exchanger_applications.find({
                "status": {"$in": ["pending", "under_review"]}
            }).sort("submitted_at", 1).limit(limit)

            applications = await cursor.to_list(length=limit)

            # Convert ObjectId to string
            for app in applications:
                app["_id"] = str(app["_id"])

            return applications

        except Exception as e:
            logger.error(f"Failed to get pending applications: {e}")
            return []

    @staticmethod
    async def update_application_status(
        application_id: str,
        status: str,
        reviewed_by: str,
        review_notes: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Update application status (admin).

        Args:
            application_id: Application ID
            status: New status (under_review, approved, rejected)
            reviewed_by: Admin user ID
            review_notes: Optional review notes

        Returns:
            Tuple of (success, message)
        """
        try:
            db = get_database()

            # Validate status
            valid_statuses = ["pending", "under_review", "approved", "rejected"]
            if status not in valid_statuses:
                return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"

            # Get application
            application = await db.exchanger_applications.find_one({
                "_id": ObjectId(application_id)
            })

            if not application:
                return False, "Application not found"

            # Update application
            update_data = {
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            if review_notes:
                update_data["review_notes"] = review_notes

            await db.exchanger_applications.update_one(
                {"_id": ObjectId(application_id)},
                {"$set": update_data}
            )

            # If approved, add exchanger role to user
            if status == "approved":
                from app.core.database import get_users_collection
                users = get_users_collection()
                await users.update_one(
                    {"user_id": application["user_id"]},
                    {"$addToSet": {"roles": "exchanger"}}
                )

                logger.info(f"Approved exchanger application {application_id} for user {application['user_id']}")

            return True, f"Application {status} successfully"

        except Exception as e:
            logger.error(f"Failed to update application status: {e}")
            return False, f"Failed to update application: {str(e)}"

    @staticmethod
    async def delete_application(application_id: str) -> tuple[bool, str]:
        """
        Delete application (admin).

        Args:
            application_id: Application ID

        Returns:
            Tuple of (success, message)
        """
        try:
            db = get_database()

            result = await db.exchanger_applications.delete_one({
                "_id": ObjectId(application_id)
            })

            if result.deleted_count > 0:
                logger.info(f"Deleted exchanger application {application_id}")
                return True, "Application deleted successfully"
            else:
                return False, "Application not found"

        except Exception as e:
            logger.error(f"Failed to delete application: {e}")
            return False, f"Failed to delete application: {str(e)}"

    @staticmethod
    async def get_application_stats() -> Dict:
        """
        Get application statistics (admin).

        Returns:
            Dictionary with stats
        """
        try:
            db = get_database()

            total = await db.exchanger_applications.count_documents({})
            pending = await db.exchanger_applications.count_documents({"status": "pending"})
            under_review = await db.exchanger_applications.count_documents({"status": "under_review"})
            approved = await db.exchanger_applications.count_documents({"status": "approved"})
            rejected = await db.exchanger_applications.count_documents({"status": "rejected"})

            return {
                "total": total,
                "pending": pending,
                "under_review": under_review,
                "approved": approved,
                "rejected": rejected
            }

        except Exception as e:
            logger.error(f"Failed to get application stats: {e}")
            return {
                "total": 0,
                "pending": 0,
                "under_review": 0,
                "approved": 0,
                "rejected": 0
            }
