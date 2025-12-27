"""
Account Recovery Service
Handles generation of recovery codes and account data transfer
Allows users to recover their Afroo account if they lose Discord access
"""

import logging
import secrets
import hashlib
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from bson import ObjectId

from app.core.database import get_db_collection
from app.core.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class RecoveryService:
    """Service for account recovery and data transfer"""

    # Recovery code configuration
    CODE_LENGTH = 15  # Length of random portion (excluding AFRO- prefix)
    CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude ambiguous characters

    @staticmethod
    def _generate_recovery_code() -> str:
        """
        Generate a secure random recovery code with AFRO- prefix.

        Returns:
            Random recovery code (e.g., "AFRO-A7K9X-2X4MN-9P2Q3")
        """
        # Generate random code (15 characters)
        code = ''.join(secrets.choice(RecoveryService.CODE_CHARSET)
                      for _ in range(RecoveryService.CODE_LENGTH))

        # Format with AFRO- prefix and dashes for readability (AFRO-XXXXX-XXXXX-XXXXX)
        formatted = f"AFRO-{code[0:5]}-{code[5:10]}-{code[10:15]}"

        return formatted

    @staticmethod
    def _hash_code(code: str) -> str:
        """
        Hash a recovery code using SHA-256.

        Args:
            code: Recovery code to hash (e.g., "AFRO-XXXXX-XXXXX-XXXXX")

        Returns:
            Hex-encoded hash
        """
        # Remove dashes and convert to uppercase
        normalized = code.replace('-', '').upper()

        # SHA-256 hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    async def generate_recovery_codes(user_id: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Generate a single recovery code for user account.
        Creates encrypted backup of user data linked to this code.

        Args:
            user_id: User ID (MongoDB ObjectId as string)

        Returns:
            Tuple of (success, [single_code], error_message)
        """
        try:
            users_db = await get_db_collection("users")
            recovery_db = await get_db_collection("recovery_data")

            user_oid = ObjectId(user_id)

            # Check if user exists
            user = await users_db.find_one({"_id": user_oid})
            if not user:
                return False, [], "User not found"

            # Generate single recovery code
            recovery_code = RecoveryService._generate_recovery_code()

            # Hash code for secure storage
            hashed_code = RecoveryService._hash_code(recovery_code)

            # Create encrypted backup of user data
            backup_data = await RecoveryService._create_user_backup(user_id)

            # Encrypt the backup
            encryption_service = get_encryption_service()
            encrypted_backup = encryption_service.encrypt(json.dumps(backup_data))

            # Store recovery data
            recovery_record = {
                "user_id": user_oid,
                "discord_id": user["discord_id"],
                "recovery_code_hash": hashed_code,
                "recovery_code": recovery_code,  # Store plaintext temporarily (will be removed after shown once)
                "encrypted_backup": encrypted_backup,
                "generated_at": datetime.utcnow(),
                "used": False,
                "used_at": None,
                "transferred_to_discord_id": None
            }

            # Delete any existing recovery data for this user
            await recovery_db.delete_many({"user_id": user_oid})

            # Insert new recovery data
            await recovery_db.insert_one(recovery_record)

            logger.info(f"Generated recovery code for user {user_id}: {recovery_code}")

            return True, [recovery_code], None

        except Exception as e:
            logger.error(f"Failed to generate recovery code: {e}", exc_info=True)
            return False, [], str(e)

    @staticmethod
    async def _create_user_backup(user_id: str) -> Dict:
        """
        Create encrypted backup of user data.
        Includes wallet private keys, stats, and account info.

        Args:
            user_id: User ID

        Returns:
            Dict with backup data
        """
        try:
            users_db = await get_db_collection("users")
            wallets_db = await get_db_collection("wallets")
            stats_db = await get_db_collection("user_statistics")

            user_oid = ObjectId(user_id)

            # Get user profile
            user = await users_db.find_one({"_id": user_oid})
            if not user:
                return {}

            # Get all wallets with private keys
            wallets = await wallets_db.find({"user_id": user_oid}).to_list(length=100)

            wallet_backups = []
            encryption_service = get_encryption_service()

            for wallet in wallets:
                # Decrypt private key for backup
                encrypted_pk = wallet.get("encrypted_private_key")
                if encrypted_pk:
                    try:
                        private_key = encryption_service.decrypt_private_key(encrypted_pk)

                        wallet_backups.append({
                            "currency": wallet["currency"],
                            "address": wallet["address"],
                            "private_key": private_key,  # Will be re-encrypted in backup
                            "balance": wallet.get("balance", 0.0),
                            "created_at": wallet.get("created_at").isoformat() if wallet.get("created_at") else None
                        })
                    except Exception as e:
                        logger.error(f"Failed to decrypt wallet {wallet.get('currency')}: {e}")

            # Get user statistics
            stats = await stats_db.find_one({"user_id": user_oid})

            # Create backup
            backup = {
                "user_id": str(user_oid),
                "discord_id": user["discord_id"],
                "username": user.get("username"),
                "reputation_score": user.get("reputation_score", 100),
                "kyc_level": user.get("kyc_level", 0),
                "roles": user.get("roles", []),
                "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
                "wallets": wallet_backups,
                "statistics": {
                    "total_volume_usd": stats.get("total_volume_usd", 0.0) if stats else 0.0,
                    "completed_trades": stats.get("completed_exchanges", 0) if stats else 0,
                    "total_swaps": stats.get("total_swaps", 0) if stats else 0,
                    "reputation_score": user.get("reputation_score", 100)
                } if stats else {},
                "backup_created_at": datetime.utcnow().isoformat()
            }

            return backup

        except Exception as e:
            logger.error(f"Failed to create user backup: {e}", exc_info=True)
            return {}

    @staticmethod
    async def check_recovery_codes_exist(user_id: str) -> Tuple[bool, Optional[datetime]]:
        """
        Check if user has recovery codes generated.

        Args:
            user_id: User ID

        Returns:
            Tuple of (has_codes, generated_at)
        """
        try:
            recovery_db = await get_db_collection("recovery_data")

            recovery = await recovery_db.find_one({"user_id": ObjectId(user_id)})

            if recovery:
                return True, recovery.get("generated_at")

            return False, None

        except Exception as e:
            logger.error(f"Failed to check recovery codes: {e}", exc_info=True)
            return False, None

    @staticmethod
    async def validate_and_transfer_account(
        recovery_code: str,
        new_discord_id: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate recovery code and transfer account to new Discord ID.

        Args:
            recovery_code: The user's recovery code (AFRO-XXXXX-XXXXX-XXXXX)
            new_discord_id: New Discord ID to transfer account to

        Returns:
            Tuple of (success, transferred_data, error_message)
        """
        try:
            recovery_db = await get_db_collection("recovery_data")
            users_db = await get_db_collection("users")
            wallets_db = await get_db_collection("wallets")

            # Hash the provided code
            code_hash = RecoveryService._hash_code(recovery_code)

            # Find recovery record with this code hash
            matching_recovery = await recovery_db.find_one({"recovery_code_hash": code_hash})

            if not matching_recovery:
                return False, None, "Invalid recovery code"

            # Check if code has already been used
            if matching_recovery.get("used", False):
                return False, None, "This recovery code has already been used"

            # Check if new Discord ID already has an account
            existing_user = await users_db.find_one({"discord_id": new_discord_id})
            if existing_user:
                return False, None, "This Discord account already has an Afroo account"

            # Decrypt backup data
            encryption_service = get_encryption_service()
            backup_json = encryption_service.decrypt(matching_recovery["encrypted_backup"])
            backup_data = json.loads(backup_json)

            # Get old user
            old_user = await users_db.find_one({"_id": matching_recovery["user_id"]})
            if not old_user:
                return False, None, "Original user account not found"

            # Update user's Discord ID
            await users_db.update_one(
                {"_id": matching_recovery["user_id"]},
                {
                    "$set": {
                        "discord_id": new_discord_id,
                        "updated_at": datetime.utcnow(),
                        "account_transferred_at": datetime.utcnow(),
                        "previous_discord_id": old_user["discord_id"]
                    }
                }
            )

            # Update wallet Discord IDs (if they store it)
            await wallets_db.update_many(
                {"user_id": matching_recovery["user_id"]},
                {"$set": {"updated_at": datetime.utcnow()}}
            )

            # Mark code as used
            await recovery_db.update_one(
                {"_id": matching_recovery["_id"]},
                {
                    "$set": {
                        "used": True,
                        "used_at": datetime.utcnow(),
                        "transferred_to_discord_id": new_discord_id
                    }
                }
            )

            logger.info(
                f"Account transfer successful: {old_user['discord_id']} → {new_discord_id}"
            )

            return True, {
                "previous_discord_id": old_user["discord_id"],
                "new_discord_id": new_discord_id,
                "wallets_transferred": len(backup_data.get("wallets", [])),
                "stats": backup_data.get("statistics", {}),
                "transferred_at": datetime.utcnow().isoformat()
            }, None

        except Exception as e:
            logger.error(f"Failed to transfer account: {e}", exc_info=True)
            return False, None, str(e)

    @staticmethod
    async def get_recovery_info(user_id: str) -> Optional[Dict]:
        """
        Get recovery information for user (without showing actual code).

        Args:
            user_id: User ID

        Returns:
            Dict with recovery info or None
        """
        try:
            recovery_db = await get_db_collection("recovery_data")

            recovery = await recovery_db.find_one({"user_id": ObjectId(user_id)})

            if not recovery:
                return None

            return {
                "has_codes": True,
                "generated_at": recovery["generated_at"].isoformat() if recovery.get("generated_at") else None,
                "used": recovery.get("used", False),
                "transferred": recovery.get("transferred_to_discord_id") is not None,
                "recovery_code": recovery.get("recovery_code")  # Only available if not shown yet
            }

        except Exception as e:
            logger.error(f"Failed to get recovery info: {e}", exc_info=True)
            return None
