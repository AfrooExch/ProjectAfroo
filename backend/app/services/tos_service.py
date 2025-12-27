"""
TOS Service - Terms of Service management
Handles TOS versions, user agreements, and compliance tracking
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_db_collection

logger = logging.getLogger(__name__)


class TOSService:
    """Service for Terms of Service management"""

    # TOS categories
    TOS_CATEGORIES = [
        "general",      # General platform terms
        "exchanger",    # Exchanger-specific terms
        "wallet",       # Wallet service terms
        "swap",         # Swap service terms
        "privacy"       # Privacy policy
    ]

    # Payment method TOS categories
    PAYMENT_METHOD_TOS_CATEGORIES = [
        "paypal",       # PayPal payment method
        "cashapp",      # Cash App payment method
        "venmo",        # Venmo payment method
        "zelle",        # Zelle payment method
        "bank_transfer",# Bank transfer payment method
        "crypto",       # Cryptocurrency payment method
        "other"         # Other payment methods
    ]

    @staticmethod
    async def create_tos_version(
        category: str,
        version: str,
        content: str,
        summary: Optional[str] = None,
        effective_date: Optional[datetime] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create new TOS version.

        Args:
            category: TOS category
            version: Version string (e.g., "1.0", "2.1")
            content: Full TOS text (Markdown supported)
            summary: Brief summary of changes
            effective_date: When this version takes effect

        Returns:
            Tuple of (success, message, tos_id)
        """
        try:
            # Allow both general TOS categories and payment method categories
            all_categories = TOSService.TOS_CATEGORIES + TOSService.PAYMENT_METHOD_TOS_CATEGORIES
            if category not in all_categories:
                return False, f"Invalid category: {category}", None

            tos_db = await get_db_collection("tos_versions")

            # Check if version already exists
            existing = await tos_db.find_one({
                "category": category,
                "version": version
            })

            if existing:
                return False, f"Version {version} already exists for {category}", None

            # Create TOS version
            tos_dict = {
                "category": category,
                "version": version,
                "content": content,
                "summary": summary,
                "effective_date": effective_date or datetime.utcnow(),
                "is_active": True,
                "created_at": datetime.utcnow()
            }

            result = await tos_db.insert_one(tos_dict)
            tos_id = str(result.inserted_id)

            # Deactivate previous versions
            await tos_db.update_many(
                {
                    "category": category,
                    "_id": {"$ne": result.inserted_id}
                },
                {"$set": {"is_active": False}}
            )

            logger.info(f"Created TOS version: {category} v{version}")

            return True, "TOS version created successfully", tos_id

        except Exception as e:
            logger.error(f"Failed to create TOS version: {e}", exc_info=True)
            return False, str(e), None

    @staticmethod
    async def get_latest_tos(category: str = "general") -> Optional[Dict]:
        """
        Get latest active TOS version for category.

        Args:
            category: TOS category

        Returns:
            TOS document or None
        """
        try:
            tos_db = await get_db_collection("tos_versions")

            tos = await tos_db.find_one(
                {"category": category, "is_active": True},
                sort=[("effective_date", -1)]
            )

            if tos:
                tos["_id"] = str(tos["_id"])

            return tos

        except Exception as e:
            logger.error(f"Failed to get latest TOS: {e}")
            return None

    @staticmethod
    async def get_all_active_tos() -> Dict[str, Dict]:
        """
        Get all active TOS versions (one per category).

        Returns:
            Dict mapping category to TOS document
        """
        try:
            result = {}

            for category in TOSService.TOS_CATEGORIES:
                tos = await TOSService.get_latest_tos(category)
                if tos:
                    result[category] = tos

            return result

        except Exception as e:
            logger.error(f"Failed to get all active TOS: {e}")
            return {}

    @staticmethod
    async def record_agreement(
        user_id: str,
        tos_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Record user agreement to TOS.

        Args:
            user_id: User ID
            tos_id: TOS version ID
            ip_address: User's IP address (for audit)
            user_agent: User's user agent (for audit)

        Returns:
            Tuple of (success, message)
        """
        try:
            tos_db = await get_db_collection("tos_versions")
            agreements_db = await get_db_collection("tos_agreements")

            # Verify TOS exists
            tos = await tos_db.find_one({"_id": ObjectId(tos_id)})
            if not tos:
                return False, "TOS version not found"

            # Handle both MongoDB ObjectId and Discord ID formats
            try:
                user_id_field = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            except:
                user_id_field = user_id

            # Check if already agreed
            existing = await agreements_db.find_one({
                "user_id": user_id_field,
                "tos_id": ObjectId(tos_id)
            })

            if existing:
                return True, "Already agreed to this version"

            # Record agreement
            agreement_dict = {
                "user_id": user_id_field,
                "tos_id": ObjectId(tos_id),
                "category": tos["category"],
                "version": tos["version"],
                "ip_address": ip_address,
                "user_agent": user_agent,
                "agreed_at": datetime.utcnow()
            }

            await agreements_db.insert_one(agreement_dict)

            logger.info(
                f"User {user_id} agreed to {tos['category']} "
                f"TOS v{tos['version']}"
            )

            return True, "Agreement recorded successfully"

        except Exception as e:
            logger.error(f"Failed to record TOS agreement: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def record_all_agreements(
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Record user agreement to all active TOS versions.

        Args:
            user_id: User ID
            ip_address: User's IP address
            user_agent: User's user agent

        Returns:
            Tuple of (success, message)
        """
        try:
            active_tos = await TOSService.get_all_active_tos()

            agreements_count = 0
            for category, tos in active_tos.items():
                success, msg = await TOSService.record_agreement(
                    user_id=user_id,
                    tos_id=tos["_id"],
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                if success:
                    agreements_count += 1

            return True, f"Recorded {agreements_count} agreements"

        except Exception as e:
            logger.error(f"Failed to record all agreements: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def has_agreed_to_latest(
        user_id: str,
        category: str = "general"
    ) -> bool:
        """
        Check if user has agreed to latest TOS version.

        Args:
            user_id: User ID
            category: TOS category

        Returns:
            True if agreed to latest version
        """
        try:
            # Get latest TOS
            latest_tos = await TOSService.get_latest_tos(category)
            if not latest_tos:
                return True  # No TOS exists, consider agreed

            # Check if user agreed
            agreements_db = await get_db_collection("tos_agreements")
            agreement = await agreements_db.find_one({
                "user_id": ObjectId(user_id),
                "tos_id": ObjectId(latest_tos["_id"])
            })

            return agreement is not None

        except Exception as e:
            logger.error(f"Failed to check TOS agreement: {e}")
            return False

    @staticmethod
    async def has_agreed_to_all_latest(user_id: str) -> Dict[str, bool]:
        """
        Check if user has agreed to all latest TOS versions.

        Args:
            user_id: User ID

        Returns:
            Dict mapping category to agreement status
        """
        try:
            result = {}

            for category in TOSService.TOS_CATEGORIES:
                result[category] = await TOSService.has_agreed_to_latest(
                    user_id,
                    category
                )

            return result

        except Exception as e:
            logger.error(f"Failed to check all TOS agreements: {e}")
            return {cat: False for cat in TOSService.TOS_CATEGORIES}

    @staticmethod
    async def get_user_agreements(user_id: str) -> List[Dict]:
        """
        Get all TOS agreements for user.

        Args:
            user_id: User ID

        Returns:
            List of agreement records
        """
        try:
            agreements_db = await get_db_collection("tos_agreements")

            cursor = agreements_db.find({
                "user_id": ObjectId(user_id)
            }).sort("agreed_at", -1)

            agreements = await cursor.to_list(length=1000)

            # Serialize ObjectIds
            for agreement in agreements:
                agreement["_id"] = str(agreement["_id"])
                agreement["user_id"] = str(agreement["user_id"])
                agreement["tos_id"] = str(agreement["tos_id"])

            return agreements

        except Exception as e:
            logger.error(f"Failed to get user agreements: {e}")
            return []

    @staticmethod
    async def get_tos_history(category: str) -> List[Dict]:
        """
        Get all TOS versions for category.

        Args:
            category: TOS category

        Returns:
            List of TOS versions
        """
        try:
            tos_db = await get_db_collection("tos_versions")

            cursor = tos_db.find({
                "category": category
            }).sort("effective_date", -1)

            versions = await cursor.to_list(length=1000)

            # Serialize ObjectIds
            for version in versions:
                version["_id"] = str(version["_id"])

            return versions

        except Exception as e:
            logger.error(f"Failed to get TOS history: {e}")
            return []

    @staticmethod
    async def get_agreement_stats(tos_id: str) -> Dict:
        """
        Get statistics for TOS version.

        Args:
            tos_id: TOS version ID

        Returns:
            Dict with stats (total agreements, date range, etc.)
        """
        try:
            agreements_db = await get_db_collection("tos_agreements")

            # Count agreements
            total_agreements = await agreements_db.count_documents({
                "tos_id": ObjectId(tos_id)
            })

            # Get date range
            first_agreement = await agreements_db.find_one(
                {"tos_id": ObjectId(tos_id)},
                sort=[("agreed_at", 1)]
            )

            last_agreement = await agreements_db.find_one(
                {"tos_id": ObjectId(tos_id)},
                sort=[("agreed_at", -1)]
            )

            return {
                "tos_id": tos_id,
                "total_agreements": total_agreements,
                "first_agreement": first_agreement["agreed_at"] if first_agreement else None,
                "last_agreement": last_agreement["agreed_at"] if last_agreement else None
            }

        except Exception as e:
            logger.error(f"Failed to get agreement stats: {e}")
            return {"tos_id": tos_id, "error": str(e)}

    @staticmethod
    async def require_tos_acceptance(user_id: str) -> Dict:
        """
        Check which TOS versions user needs to accept.

        Args:
            user_id: User ID

        Returns:
            Dict with required TOS versions
        """
        try:
            agreements = await TOSService.has_agreed_to_all_latest(user_id)

            # Get TOS that haven't been agreed to
            required = []
            for category, has_agreed in agreements.items():
                if not has_agreed:
                    tos = await TOSService.get_latest_tos(category)
                    if tos:
                        required.append({
                            "category": category,
                            "version": tos["version"],
                            "tos_id": tos["_id"],
                            "summary": tos.get("summary"),
                            "content": tos["content"]
                        })

            return {
                "user_id": user_id,
                "requires_acceptance": len(required) > 0,
                "required_tos": required
            }

        except Exception as e:
            logger.error(f"Failed to check required TOS: {e}")
            return {"user_id": user_id, "error": str(e)}

    @staticmethod
    async def get_tos_for_ticket(
        send_method: str,
        receive_method: str
    ) -> Dict[str, Dict]:
        """
        Get TOS required for an exchange ticket.
        Returns general TOS + custom TOS for both payment methods.

        Args:
            send_method: Payment method for sending (e.g., "paypal", "cashapp")
            receive_method: Payment method for receiving (e.g., "crypto", "zelle")

        Returns:
            Dict with general_tos, send_method_tos, receive_method_tos
        """
        try:
            result = {}

            # Get general TOS (always required)
            general_tos = await TOSService.get_latest_tos("general")
            if general_tos:
                result["general"] = general_tos

            # Get TOS for send method (if exists)
            send_method_lower = send_method.lower().replace(" ", "_")
            if send_method_lower in TOSService.PAYMENT_METHOD_TOS_CATEGORIES:
                send_tos = await TOSService.get_latest_tos(send_method_lower)
                if send_tos:
                    result[f"send_method_{send_method_lower}"] = send_tos

            # Get TOS for receive method (if exists)
            receive_method_lower = receive_method.lower().replace(" ", "_")
            if receive_method_lower in TOSService.PAYMENT_METHOD_TOS_CATEGORIES:
                receive_tos = await TOSService.get_latest_tos(receive_method_lower)
                if receive_tos:
                    result[f"receive_method_{receive_method_lower}"] = receive_tos

            return result

        except Exception as e:
            logger.error(f"Failed to get TOS for ticket: {e}")
            return {}


# Initial TOS setup (to be run once)
async def initialize_default_tos():
    """
    Initialize default TOS versions.
    Should be run once during platform setup.
    """
    try:
        # General TOS
        await TOSService.create_tos_version(
            category="general",
            version="1.0",
            content="""# Afroo Exchange Terms of Service

## 1. Acceptance of Terms
By using Afroo Exchange, you agree to these terms of service.

## 2. Service Description
Afroo Exchange is a cryptocurrency exchange platform connecting users for peer-to-peer exchanges.

## 3. User Responsibilities
- You must be 18 years or older
- You are responsible for account security
- You must comply with all applicable laws

## 4. Prohibited Activities
- Fraud, scams, or deceptive practices
- Money laundering or illegal activities
- Violating other users' rights

## 5. Dispute Resolution
Disputes will be resolved through platform arbitration.

## 6. Limitation of Liability
Afroo Exchange is not liable for user losses or disputes.

## 7. Changes to Terms
We reserve the right to modify these terms at any time.

Last updated: {datetime.utcnow().strftime('%Y-%m-%d')}
""",
            summary="Initial Terms of Service",
            effective_date=datetime.utcnow()
        )

        # Exchanger TOS
        await TOSService.create_tos_version(
            category="exchanger",
            version="1.0",
            content="""# Exchanger Terms

## Exchanger Responsibilities
- Provide accurate exchange rates
- Complete exchanges in timely manner
- Maintain sufficient liquidity
- Respond to support tickets

## Fees
- Platform fee: 1% of exchange amount
- Hold system protects against fraud

## Rating System
Your performance affects your reputation score.
""",
            summary="Exchanger-specific terms",
            effective_date=datetime.utcnow()
        )

        logger.info("Default TOS versions initialized")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize default TOS: {e}", exc_info=True)
        return False
