"""
API Client - Main client for backend API communication
Handles JWT authentication, requests, and error translation
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from api.errors import (
    APIError, AuthenticationError, PermissionError,
    NotFoundError, RateLimitError, ValidationError, ServerError
)
from models import (
    User, Ticket, Wallet, Swap, SupportTicket, Transaction,
    CustomerStats, ExchangerStats, APIResponse
)

logger = logging.getLogger(__name__)


class APIClient:
    """
    API Client for backend communication

    Handles:
    - JWT authentication with automatic refresh
    - HTTP requests with retry logic
    - Error translation to user-friendly messages
    - Response parsing to Pydantic models
    """

    def __init__(self, base_url: str, bot_service_token: str):
        """
        Initialize API client

        Args:
            base_url: Base URL of API (e.g., http://localhost:8001)
            bot_service_token: Bot service authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.bot_service_token = bot_service_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Initialize HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        logger.info("API client connected")

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("API client closed")

    # =======================
    # Helper Methods
    # =======================

    def _get_user_roles(self, member) -> List[int]:
        """Extract role IDs from Discord member"""
        if not member or not hasattr(member, 'roles'):
            return []
        return [role.id for role in member.roles]

    # =======================
    # HTTP Methods
    # =======================

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and user context

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /api/v1/tickets)
            data: JSON body data
            params: Query parameters
            discord_user_id: Discord user ID for authentication context
            discord_roles: List of Discord role IDs for permission validation
            max_retries: Maximum retry attempts

        Returns:
            Response JSON data

        Raises:
            APIError: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.bot_service_token}",
            "X-Bot-Token": self.bot_service_token,  # For bot-authenticated endpoints
            "Content-Type": "application/json"
        }

        # Add user context headers if provided
        if discord_user_id:
            headers["X-Discord-User-ID"] = str(discord_user_id)
            headers["X-Discord-ID"] = str(discord_user_id)  # Alternative header name
            headers["X-User-ID"] = str(discord_user_id)  # V4 Wallet API uses this

        if discord_roles:
            headers["X-Discord-Roles"] = ",".join(str(role_id) for role_id in discord_roles)

        for attempt in range(max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    # Get response data
                    try:
                        response_data = await resp.json()
                    except:
                        response_data = {}

                    # Success
                    if 200 <= resp.status < 300:
                        return response_data

                    # Rate limit
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "60"))
                        raise RateLimitError(
                            "Rate limit exceeded",
                            retry_after=retry_after,
                            response_data=response_data
                        )

                    # Client errors (don't retry)
                    if 400 <= resp.status < 500:
                        error_class = self._get_error_class(resp.status)
                        # Extract error message from response detail
                        error_message = response_data.get("detail", f"Request failed: {resp.status}")
                        raise error_class(
                            error_message,
                            status_code=resp.status,
                            response_data=response_data
                        )

                    # Server errors (retry with backoff)
                    if resp.status >= 500:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise ServerError(
                            f"Server error: {resp.status}",
                            status_code=resp.status,
                            response_data=response_data
                        )

            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise APIError(f"Network error: {e}")

        raise APIError("Max retries exceeded")

    @staticmethod
    def _get_error_class(status_code: int):
        """Get appropriate error class for status code"""
        if status_code == 401:
            return AuthenticationError
        elif status_code == 403:
            return PermissionError
        elif status_code == 404:
            return NotFoundError
        elif status_code == 400 or status_code == 422:
            return ValidationError
        elif status_code == 429:
            return RateLimitError
        else:
            return APIError

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict:
        """GET request"""
        return await self._request(
            "GET",
            endpoint,
            params=params,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict:
        """POST request"""
        return await self._request(
            "POST",
            endpoint,
            data=data,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict:
        """PUT request"""
        return await self._request(
            "PUT",
            endpoint,
            data=data,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )

    async def patch(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict:
        """PATCH request"""
        return await self._request(
            "PATCH",
            endpoint,
            data=data,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )

    async def delete(
        self,
        endpoint: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict:
        """DELETE request"""
        return await self._request(
            "DELETE",
            endpoint,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )

    # =======================
    # Health Check
    # =======================

    async def health_check(self) -> bool:
        """
        Check API health

        Returns:
            True if API is healthy
        """
        try:
            data = await self.get("/health")
            return data.get("status") == "healthy"
        except:
            return False

    # =======================
    # User Operations
    # =======================

    async def get_user(self, discord_id: str) -> User:
        """
        Get user by Discord ID

        Args:
            discord_id: Discord user ID

        Returns:
            User object
        """
        data = await self.get(f"/api/v1/users/{discord_id}")
        return User(**data)

    async def register_user(
        self,
        discord_id: str,
        username: str,
        discriminator: str,
        avatar: Optional[str] = None
    ) -> User:
        """
        Register new user

        Args:
            discord_id: Discord user ID
            username: Discord username
            discriminator: Discord discriminator
            avatar: Avatar hash

        Returns:
            Created user object
        """
        data = await self.post("/api/v1/users", {
            "discord_id": discord_id,
            "username": username,
            "discriminator": discriminator,
            "avatar": avatar
        })
        return User(**data)

    async def get_customer_stats(self, user_id: str) -> CustomerStats:
        """Get customer statistics"""
        data = await self.get(f"/api/v1/users/{user_id}/stats")
        return CustomerStats(**data)

    async def get_exchanger_stats(self, user_id: str) -> ExchangerStats:
        """Get exchanger statistics"""
        data = await self.get(f"/api/v1/exchangers/{user_id}/stats")
        return ExchangerStats(**data)

    # =======================
    # Ticket Operations
    # =======================

    async def create_ticket(
        self,
        user_id: str,
        input_currency: str,
        output_currency: str,
        amount: float
    ) -> Ticket:
        """Create exchange ticket"""
        data = await self.post("/api/v1/tickets", {
            "user_id": user_id,
            "input_currency": input_currency,
            "output_currency": output_currency,
            "amount": amount
        })
        return Ticket(**data)

    async def create_exchange_ticket(
        self,
        user_id: str,
        username: str,
        send_method: str,
        receive_method: str,
        amount_usd: float,
        fee_amount: float,
        fee_percentage: float,
        receiving_amount: float,
        send_crypto: Optional[str] = None,
        receive_crypto: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create V4 exchange ticket"""
        data = await self.post("/api/v1/tickets/create", {
            "user_id": user_id,
            "username": username,
            "send_method": send_method,
            "receive_method": receive_method,
            "amount_usd": amount_usd,
            "fee_amount": fee_amount,
            "fee_percentage": fee_percentage,
            "receiving_amount": receiving_amount,
            "send_crypto": send_crypto,
            "receive_crypto": receive_crypto
        })
        return data

    async def get_ticket(
        self,
        ticket_id: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Get ticket by ID - returns raw dict (V4 API)"""
        data = await self.get(
            f"/api/v1/tickets/{ticket_id}",
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        # API returns {"ticket": {...}, "messages": [...]}
        ticket_data = data.get("ticket") if isinstance(data, dict) and "ticket" in data else data
        return ticket_data  # Return raw dict instead of parsing to outdated Ticket model

    async def update_ticket(
        self,
        ticket_id: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None,
        **kwargs
    ) -> Ticket:
        """Update ticket"""
        data = await self.patch(
            f"/api/v1/tickets/{ticket_id}",
            kwargs,
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        return Ticket(**data)

    async def claim_ticket(
        self,
        ticket_id: str,
        exchanger_id: str,
        exchanger_username: Optional[str] = None,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Claim ticket with balance check and hold creation"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/claim",
            {
                "exchanger_id": exchanger_id,
                "exchanger_username": exchanger_username
            },
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        return data

    async def unclaim_ticket(
        self,
        ticket_id: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Ticket:
        """Unclaim ticket"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/unclaim",
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        return Ticket(**data)

    async def complete_ticket(
        self,
        ticket_id: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Complete ticket - releases holds, updates stats"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/complete",
            data={},
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        return data

    async def process_internal_payout(
        self,
        ticket_id: str,
        wallet_address: str,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process internal payout (from locked funds)"""
        payload = {"wallet_address": wallet_address}
        if currency:
            payload["currency"] = currency
        data = await self.post(f"/api/v1/tickets/{ticket_id}/internal-payout", payload)
        return data

    async def process_external_payout(
        self,
        ticket_id: str,
        tx_hash: str,
        wallet_address: str,
        discord_user_id: Optional[str] = None,
        discord_roles: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Process external payout (verify TXID)"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/external-payout",
            {
                "client_address": wallet_address,
                "tx_hash": tx_hash
            },
            discord_user_id=discord_user_id,
            discord_roles=discord_roles
        )
        return data

    async def accept_tos(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Accept TOS for exchange ticket"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/accept-tos",
            data={},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def accept_ticket_tos(self, ticket_id: str) -> Dict[str, Any]:
        """Accept TOS for exchange ticket (simplified - no user context needed)"""
        try:
            data = await self.post(f"/api/v1/tickets/{ticket_id}/tos/agree", data={"agreed": True})
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Error accepting TOS: {e}")
            return {"success": False, "error": str(e)}

    async def deny_tos(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Deny TOS for exchange ticket (will cancel/expire ticket)"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/deny-tos",
            data={},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def cancel_ticket(self, ticket_id: str, reason: str = "") -> Dict[str, Any]:
        """Cancel ticket (simplified - no user context needed)"""
        try:
            data = await self.post(f"/api/v1/tickets/{ticket_id}/cancel", data={"reason": reason})
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Error canceling ticket: {e}")
            return {"success": False, "error": str(e)}

    async def update_ticket_status(
        self,
        ticket_id: str,
        status: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Update ticket status"""
        data = await self.patch(
            f"/api/v1/tickets/{ticket_id}/status",
            data={"status": status},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def mark_client_sent(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Mark that client has sent their funds"""
        data = await self.post(
            f"/api/v1/tickets/{ticket_id}/client-sent",
            data={},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # V4 Crypto Wallet Operations
    # =======================

    async def v4_generate_wallet(self, user_id: str, currency: str) -> dict:
        """Generate V4 crypto wallet for currency"""
        response = await self._request(
            "POST",
            f"/api/v1/wallet/{currency}/generate",
            discord_user_id=user_id
        )
        return response.get("data", {})

    async def v4_get_wallet(self, user_id: str, currency: str) -> dict:
        """Get V4 wallet details for currency"""
        response = await self._request(
            "GET",
            f"/api/v1/wallet/{currency}",
            discord_user_id=user_id
        )
        return response.get("data", {})

    async def v4_get_portfolio(self, user_id: str) -> dict:
        """Get all V4 wallet balances"""
        response = await self._request(
            "GET",
            "/api/v1/wallet/portfolio",
            discord_user_id=user_id
        )
        return response.get("data", {})

    async def v4_sync_wallet(self, user_id: str, currency: str) -> dict:
        """Sync wallet balance with blockchain"""
        response = await self._request(
            "POST",
            f"/api/v1/wallet/{currency}/sync",
            discord_user_id=user_id
        )
        return response.get("data", {})

    async def v4_withdraw_preview(self, user_id: str, currency: str, amount: str) -> dict:
        """Preview withdrawal fees"""
        response = await self._request(
            "POST",
            f"/api/v1/wallet/{currency}/withdraw/preview",
            discord_user_id=user_id,
            params={"amount": amount}
        )
        return response.get("data", {})

    async def v4_withdraw(self, user_id: str, currency: str, to_address: str, amount: str, network_fee: str = None, server_fee: str = None, total_deducted: str = None) -> dict:
        """Withdraw crypto to external address"""
        data = {"to_address": to_address, "amount": amount}

        # Include precomputed fees if provided (for max withdrawals)
        if network_fee and server_fee and total_deducted:
            data["network_fee"] = network_fee
            data["server_fee"] = server_fee
            data["total_deducted"] = total_deducted

        response = await self._request(
            "POST",
            f"/api/v1/wallet/{currency}/withdraw",
            discord_user_id=user_id,
            data=data
        )
        return response.get("data", {})

    async def v4_get_transactions(self, user_id: str, currency: str, limit: int = 10) -> dict:
        """Get wallet transaction history"""
        response = await self._request(
            "GET",
            f"/api/v1/wallet/{currency}/transactions",
            discord_user_id=user_id,
            params={"limit": limit}
        )
        return response.get("data", {})

    # =======================
    # Admin Operations
    # =======================

    async def get_all_tickets(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Ticket]:
        """Get all tickets (admin)"""
        params = {"limit": limit}
        if status:
            params["status"] = status

        data = await self.get("/api/v1/admin/tickets", params=params)
        return [Ticket(**t) for t in data.get("items", [])]

    async def freeze_user(self, user_id: str, reason: str) -> User:
        """Freeze user account"""
        data = await self.post(f"/api/v1/admin/users/{user_id}/freeze", {
            "reason": reason
        })
        return User(**data)

    async def unfreeze_user(self, user_id: str) -> User:
        """Unfreeze user account"""
        data = await self.post(f"/api/v1/admin/users/{user_id}/unfreeze")
        return User(**data)

    # =======================
    # Role Syncing (CRITICAL)
    # =======================

    async def sync_roles(
        self,
        discord_id: str,
        role_ids: List[int],
        username: str,
        discriminator: str,
        global_name: Optional[str] = None,
        avatar_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync Discord roles to API database

        This is critical for authentication and permission validation.
        Should be called:
        - On bot startup for all members
        - On member_update events
        - Before any authenticated API call

        Args:
            discord_id: Discord user ID
            role_ids: List of Discord role IDs
            username: Discord username
            discriminator: Discord discriminator (e.g., "0001")
            global_name: Discord global/display name
            avatar_hash: Discord avatar hash

        Returns:
            Updated user data
        """
        data = await self.post(
            "/api/v1/users/sync-roles",
            data={
                "discord_id": str(discord_id),
                "role_ids": role_ids,
                "username": username,
                "discriminator": discriminator,
                "global_name": global_name,
                "avatar_hash": avatar_hash
            },
            discord_user_id=str(discord_id),
            discord_roles=role_ids
        )
        return data

    async def update_user(
        self,
        discord_id: str,
        discord_roles: List[int],
        **updates
    ) -> User:
        """
        Update user profile

        Args:
            discord_id: Discord user ID
            discord_roles: User's Discord role IDs (for auth)
            **updates: Fields to update (username, avatar, etc.)

        Returns:
            Updated user object
        """
        data = await self.patch(
            f"/api/v1/users/{discord_id}",
            data=updates,
            discord_user_id=str(discord_id),
            discord_roles=discord_roles
        )
        return User(**data)

    # =======================
    # Support Ticket Operations
    # =======================

    async def create_support_ticket(
        self,
        user_id: str,
        discord_roles: List[int],
        ticket_type: str,
        subject: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Create support ticket (Bug Report, Feature Request, General Support)

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            ticket_type: "bug_report", "feature_request", "general_support"
            subject: Ticket subject/title
            description: Detailed description

        Returns:
            Created ticket data with channel_id
        """
        data = await self.post(
            "/api/v1/support/tickets",
            data={
                "user_id": user_id,
                "ticket_type": ticket_type,
                "subject": subject,
                "description": description
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_support_ticket(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Get support ticket by ID"""
        data = await self.get(
            f"/api/v1/support/tickets/{ticket_id}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def close_support_ticket(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Close support ticket"""
        data = await self.post(
            f"/api/v1/support/tickets/{ticket_id}/close",
            data={"reason": reason} if reason else {},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def add_support_ticket_message(
        self,
        ticket_id: str,
        user_id: str,
        discord_roles: List[int],
        message: str,
        attachments: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add message to support ticket"""
        data = await self.post(
            f"/api/v1/support/tickets/{ticket_id}/messages",
            data={
                "message": message,
                "attachments": attachments or []
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Application Operations
    # =======================

    async def create_application(
        self,
        user_id: str,
        discord_roles: List[int],
        application_type: str,
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Create application (Exchanger, Staff)

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            application_type: "exchanger" or "staff"
            answers: Dictionary of question-answer pairs

        Returns:
            Created application data with channel_id
        """
        data = await self.post(
            "/api/v1/applications",
            data={
                "user_id": user_id,
                "application_type": application_type,
                "answers": answers
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_application(
        self,
        application_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Get application by ID"""
        data = await self.get(
            f"/api/v1/applications/{application_id}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def update_application(
        self,
        application_id: str,
        user_id: str,
        discord_roles: List[int],
        **updates
    ) -> Dict[str, Any]:
        """Update application status/notes"""
        data = await self.patch(
            f"/api/v1/applications/{application_id}",
            data=updates,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def approve_application(
        self,
        application_id: str,
        admin_id: str,
        discord_roles: List[int],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Approve application (admin only)"""
        data = await self.post(
            f"/api/v1/applications/{application_id}/approve",
            data={"notes": notes} if notes else {},
            discord_user_id=admin_id,
            discord_roles=discord_roles
        )
        return data

    async def reject_application(
        self,
        application_id: str,
        admin_id: str,
        discord_roles: List[int],
        reason: str
    ) -> Dict[str, Any]:
        """Reject application (admin only)"""
        data = await self.post(
            f"/api/v1/applications/{application_id}/reject",
            data={"reason": reason},
            discord_user_id=admin_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Swap Operations
    # =======================

    async def get_swap_estimate(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """
        Get swap estimate from ChangeNow

        Args:
            from_currency: Source currency (e.g., "BTC")
            to_currency: Destination currency (e.g., "ETH")
            amount: Amount to swap
            user_id: Discord user ID
            discord_roles: User's role IDs

        Returns:
            Estimate data with rate, minimum, fees
        """
        data = await self.get(
            "/api/v1/swaps/estimate",
            params={
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": amount
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def create_swap(
        self,
        user_id: str,
        discord_roles: List[int],
        from_currency: str,
        to_currency: str,
        amount: float,
        destination_address: str
    ) -> Dict[str, Any]:
        """
        Create swap transaction

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            from_currency: Source currency
            to_currency: Destination currency
            amount: Amount to swap
            destination_address: User's receiving address

        Returns:
            Swap data with deposit_address and swap_id
        """
        data = await self.post(
            "/api/v1/swaps",
            data={
                "user_id": user_id,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": amount,
                "destination_address": destination_address
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_swap(
        self,
        swap_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Get swap by ID"""
        data = await self.get(
            f"/api/v1/swaps/{swap_id}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_user_swaps(
        self,
        user_id: str,
        discord_roles: List[int],
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's swap history"""
        params = {"limit": limit}
        if status:
            params["status"] = status

        data = await self.get(
            f"/api/v1/swaps/user/{user_id}",
            params=params,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data.get("items", [])

    # =======================
    # Afroo Swap Operations (ChangeNOW)
    # =======================

    async def afroo_swap_get_quote(
        self,
        from_asset: str,
        to_asset: str,
        amount: float,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """
        Get Afroo Swap quote with platform fees

        Args:
            from_asset: Source asset (e.g., "BTC", "ETH", "SOL")
            to_asset: Destination asset
            amount: Amount to swap
            user_id: Discord user ID
            discord_roles: User's role IDs

        Returns:
            Quote data with exchange_rate, estimated_output, platform_fee, etc.
        """
        data = await self.post(
            "/api/v1/afroo-swaps/quote",
            data={
                "from_asset": from_asset,
                "to_asset": to_asset,
                "amount": amount
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def afroo_swap_execute(
        self,
        from_asset: str,
        to_asset: str,
        amount: float,
        destination_address: str,
        user_id: str,
        discord_roles: List[int],
        refund_address: Optional[str] = None,
        slippage_tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        Execute Afroo Swap via ChangeNOW - creates exchange order

        Args:
            from_asset: Source asset
            to_asset: Destination asset
            amount: Amount to swap
            destination_address: Where user wants to receive swapped crypto
            user_id: Discord user ID
            discord_roles: User's role IDs
            refund_address: Where to refund if swap fails (optional)
            slippage_tolerance: Max acceptable slippage (default 1%)

        Returns:
            Swap data with swap_id, changenow_deposit_address, status
        """
        request_data = {
            "from_asset": from_asset,
            "to_asset": to_asset,
            "amount": amount,
            "destination_address": destination_address,
            "slippage_tolerance": slippage_tolerance
        }

        if refund_address:
            request_data["refund_address"] = refund_address

        data = await self.post(
            "/api/v1/afroo-swaps/execute",
            data=request_data,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def afroo_swap_get_details(
        self,
        swap_id: str,
        user_id: str,
        discord_roles: List[int],
        refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get Afroo Swap details by ID

        Args:
            swap_id: Swap ID
            user_id: Discord user ID
            discord_roles: User's role IDs
            refresh: If True, refresh status from ChangeNOW before returning
        """
        params = {}
        if refresh:
            params["refresh"] = "true"

        data = await self.get(
            f"/api/v1/afroo-swaps/{swap_id}",
            params=params,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def afroo_swap_get_history(
        self,
        user_id: str,
        discord_roles: List[int],
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's Afroo Swap history

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            limit: Number of swaps to return
            status: Filter by status (optional)

        Returns:
            List of swap records
        """
        params = {"limit": limit}
        if status:
            params["status"] = status

        data = await self.get(
            "/api/v1/afroo-swaps/history",
            params=params,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data.get("swaps", [])

    async def afroo_swap_get_supported_assets(self) -> List[str]:
        """
        Get list of supported assets for Afroo Swap

        Returns:
            List of asset tickers (e.g., ["BTC", "ETH", "SOL", ...])
        """
        data = await self.get("/api/v1/afroo-swaps/supported-assets")
        return data.get("assets", [])

    # =======================
    # AutoMM / Escrow Operations
    # =======================

    async def create_escrow(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: str,
        amount: float,
        recipient_id: str,
        terms: str
    ) -> Dict[str, Any]:
        """
        Create AutoMM escrow transaction

        Args:
            user_id: Discord user ID (creator)
            discord_roles: User's role IDs
            asset: Cryptocurrency asset
            amount: Amount in escrow
            recipient_id: Discord ID of recipient
            terms: Escrow terms/description

        Returns:
            Escrow data with escrow_id and deposit_address
        """
        data = await self.post(
            "/api/v1/escrow",
            data={
                "user_id": user_id,
                "asset": asset,
                "amount": amount,
                "recipient_id": recipient_id,
                "terms": terms
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_escrow(
        self,
        escrow_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Get escrow by ID"""
        data = await self.get(
            f"/api/v1/escrow/{escrow_id}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def complete_escrow(
        self,
        escrow_id: str,
        user_id: str,
        discord_roles: List[int],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete escrow and release funds"""
        data = await self.post(
            f"/api/v1/escrow/{escrow_id}/complete",
            data={"notes": notes} if notes else {},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def cancel_escrow(
        self,
        escrow_id: str,
        user_id: str,
        discord_roles: List[int],
        reason: str
    ) -> Dict[str, Any]:
        """Cancel escrow and refund"""
        data = await self.post(
            f"/api/v1/escrow/{escrow_id}/cancel",
            data={"reason": reason},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def dispute_escrow(
        self,
        escrow_id: str,
        user_id: str,
        discord_roles: List[int],
        reason: str
    ) -> Dict[str, Any]:
        """Dispute escrow (opens admin ticket)"""
        data = await self.post(
            f"/api/v1/escrow/{escrow_id}/dispute",
            data={"reason": reason},
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Transaction Operations
    # =======================

    async def get_transactions(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: Optional[str] = None,
        transaction_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user's transaction history

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            asset: Filter by asset (optional)
            transaction_type: Filter by type (deposit, withdrawal, etc.)
            limit: Number of transactions to return

        Returns:
            List of transaction records
        """
        params = {"limit": limit}
        if asset:
            params["asset"] = asset
        if transaction_type:
            params["type"] = transaction_type

        data = await self.get(
            f"/api/v1/transactions/user/{user_id}",
            params=params,
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data.get("items", [])

    async def get_transaction(
        self,
        tx_id: str,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """Get transaction by ID"""
        data = await self.get(
            f"/api/v1/transactions/{tx_id}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Wallet Operations (Extended)
    # =======================

    async def get_wallet(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: str
    ) -> Dict[str, Any]:
        """Get specific wallet by asset"""
        data = await self.get(
            f"/api/v1/wallets/user/{user_id}/asset/{asset}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def create_wallet(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: str,
        network: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create/generate new wallet for asset"""
        data = await self.post(
            "/api/v1/wallets/generate",
            data={
                "user_id": user_id,
                "asset": asset,
                "network": network
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def get_deposit_address(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: str
    ) -> Dict[str, Any]:
        """
        Get deposit address for asset (creates wallet if needed)

        Returns:
            Dict with address, qr_code_url, asset, network
        """
        data = await self.get(
            f"/api/v1/wallets/deposit-address/{asset}",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def withdraw(
        self,
        user_id: str,
        discord_roles: List[int],
        asset: str,
        amount: float,
        destination_address: str,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw funds to external address

        Args:
            user_id: Discord user ID
            discord_roles: User's role IDs
            asset: Asset to withdraw
            amount: Amount to withdraw
            destination_address: External wallet address
            memo: Optional memo/tag (for XRP, etc.)

        Returns:
            Withdrawal transaction data
        """
        data = await self.post(
            "/api/v1/wallets/withdraw",
            data={
                "user_id": user_id,
                "asset": asset,
                "amount": amount,
                "destination_address": destination_address,
                "memo": memo
            },
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    async def internal_transfer(
        self,
        from_user_id: str,
        discord_roles: List[int],
        to_user_id: str,
        asset: str,
        amount: float,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transfer funds internally between users

        Args:
            from_user_id: Sender's Discord ID
            discord_roles: Sender's role IDs
            to_user_id: Recipient's Discord ID
            asset: Asset to transfer
            amount: Amount to transfer
            note: Optional note

        Returns:
            Transfer transaction data
        """
        data = await self.post(
            "/api/v1/wallets/transfer",
            data={
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "asset": asset,
                "amount": amount,
                "note": note
            },
            discord_user_id=from_user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Leaderboard & Stats
    # =======================

    async def get_leaderboard(
        self,
        leaderboard_type: str = "customer",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard

        Args:
            leaderboard_type: "customer" or "exchanger"
            limit: Number of entries

        Returns:
            List of leaderboard entries
        """
        data = await self.get(
            "/api/v1/stats/leaderboard",
            params={
                "type": leaderboard_type,
                "limit": limit
            }
        )
        return data.get("items", [])

    async def get_platform_stats(
        self,
        admin_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """
        Get platform-wide statistics (admin only)

        Returns:
            Dict with total users, tickets, volume, etc.
        """
        data = await self.get(
            "/api/v1/stats/platform",
            discord_user_id=admin_id,
            discord_roles=discord_roles
        )
        return data

    async def get_user_dashboard(
        self,
        user_id: str,
        discord_roles: List[int]
    ) -> Dict[str, Any]:
        """
        Get comprehensive user dashboard data

        Returns:
            Dict with stats, wallets, recent transactions, tickets
        """
        data = await self.get(
            f"/api/v1/users/{user_id}/dashboard",
            discord_user_id=user_id,
            discord_roles=discord_roles
        )
        return data

    # =======================
    # Deposit Operations
    # =======================

    async def create_deposit_wallet(
        self,
        exchanger_id: str,
        discord_roles: List[int],
        asset: str
    ) -> Dict[str, Any]:
        """
        Create deposit wallet for exchanger

        Returns:
            Wallet data with address for deposits
        """
        data = await self.post(
            "/api/v1/deposits/create-wallet",
            data={
                "exchanger_id": exchanger_id,
                "asset": asset
            },
            discord_user_id=exchanger_id,
            discord_roles=discord_roles
        )
        return data

    async def get_deposit_wallets(
        self,
        exchanger_id: str,
        discord_roles: List[int]
    ) -> List[Dict[str, Any]]:
        """Get all deposit wallets for exchanger"""
        data = await self.get(
            f"/api/v1/deposits/wallets/{exchanger_id}",
            discord_user_id=exchanger_id,
            discord_roles=discord_roles
        )
        return data.get("wallets", [])

    async def get_pending_deposits(
        self,
        exchanger_id: str,
        discord_roles: List[int]
    ) -> List[Dict[str, Any]]:
        """Get pending deposit transactions"""
        data = await self.get(
            f"/api/v1/deposits/pending/{exchanger_id}",
            discord_user_id=exchanger_id,
            discord_roles=discord_roles
        )
        return data.get("deposits", [])

    # =======================
    # Exchanger Deposit Operations (V4)
    # =======================

    async def exchanger_create_deposit(self, user_id: str, currency: str) -> dict:
        """
        Create exchanger deposit wallet for currency
        Generates separate wallet from regular V4 wallet
        """
        response = await self._request(
            "POST",
            "/api/v1/exchanger/deposits/create",
            data={"currency": currency},
            discord_user_id=user_id
        )
        return response

    async def exchanger_list_deposits(self, user_id: str) -> dict:
        """Get all exchanger deposit wallets for user"""
        response = await self._request(
            "GET",
            "/api/v1/exchanger/deposits/list",
            discord_user_id=user_id
        )
        return response

    async def exchanger_get_deposit(self, user_id: str, currency: str) -> dict:
        """Get specific exchanger deposit wallet"""
        response = await self._request(
            "GET",
            f"/api/v1/exchanger/deposits/{currency}",
            discord_user_id=user_id
        )
        return response

    async def exchanger_sync_deposit(self, user_id: str, currency: str) -> dict:
        """Sync exchanger deposit balance from blockchain"""
        response = await self._request(
            "POST",
            f"/api/v1/exchanger/deposits/{currency}/sync",
            discord_user_id=user_id
        )
        return response

    async def exchanger_get_claim_limit(self, user_id: str) -> dict:
        """
        Get exchanger claim limit information
        Shows total deposits, held, and available claim capacity (1:1 ratio)
        """
        response = await self._request(
            "GET",
            "/api/v1/exchanger/claim-limit",
            discord_user_id=user_id
        )
        return response

    async def exchanger_withdraw(
        self,
        user_id: str,
        currency: str,
        amount: str,
        to_address: str
    ) -> dict:
        """
        Withdraw from exchanger deposit (only free funds)
        Server fees already reserved, only network fee calculated
        """
        response = await self._request(
            "POST",
            "/api/v1/exchanger/withdraw",
            data={
                "currency": currency,
                "amount": amount,
                "to_address": to_address
            },
            discord_user_id=user_id
        )
        return response

    async def exchanger_get_history(
        self,
        user_id: str,
        currency: Optional[str] = None,
        limit: int = 50
    ) -> dict:
        """Get exchanger transaction history"""
        params = {"limit": limit}
        if currency:
            params["currency"] = currency

        response = await self._request(
            "GET",
            "/api/v1/exchanger/history",
            params=params,
            discord_user_id=user_id
        )
        return response

    # ====================
    # Exchanger Preferences
    # ====================

    async def exchanger_get_preferences(self, user_id: str) -> dict:
        """Get exchanger role preferences"""
        response = await self._request(
            "GET",
            "/api/v1/exchanger/preferences",
            discord_user_id=user_id
        )
        return response

    async def exchanger_update_preferences(
        self,
        user_id: str,
        preferred_payment_methods: Optional[List[str]] = None,
        preferred_currencies: Optional[List[str]] = None,
        min_ticket_amount: Optional[str] = None,
        max_ticket_amount: Optional[str] = None,
        notifications_enabled: Optional[bool] = None
    ) -> dict:
        """Update exchanger preferences"""
        data = {}
        if preferred_payment_methods is not None:
            data["preferred_payment_methods"] = preferred_payment_methods
        if preferred_currencies is not None:
            data["preferred_currencies"] = preferred_currencies
        if min_ticket_amount is not None:
            data["min_ticket_amount"] = min_ticket_amount
        if max_ticket_amount is not None:
            data["max_ticket_amount"] = max_ticket_amount
        if notifications_enabled is not None:
            data["notifications_enabled"] = notifications_enabled

        response = await self._request(
            "PUT",
            "/api/v1/exchanger/preferences",
            data=data,
            discord_user_id=user_id
        )
        return response

    # ====================
    # Exchanger Questions
    # ====================

    async def exchanger_get_preset_questions(self) -> dict:
        """Get list of 13 preset questions"""
        response = await self._request(
            "GET",
            "/api/v1/exchanger/questions/preset"
        )
        return response

    async def exchanger_get_awaiting_tickets(self, user_id: str, limit: int = 25) -> dict:
        """Get tickets awaiting claim (for asking questions)"""
        response = await self._request(
            "GET",
            "/api/v1/exchanger/questions/tickets",
            params={"limit": limit},
            discord_user_id=user_id
        )
        return response

    async def exchanger_ask_question(
        self,
        user_id: str,
        ticket_id: str,
        question_text: str,
        question_type: str = "preset",
        alt_payment_method: Optional[str] = None,
        alt_amount_usd: Optional[str] = None
    ) -> dict:
        """Ask anonymous question on ticket"""
        data = {
            "ticket_id": ticket_id,
            "question_text": question_text,
            "question_type": question_type
        }

        if alt_payment_method:
            data["alt_payment_method"] = alt_payment_method
        if alt_amount_usd:
            data["alt_amount_usd"] = alt_amount_usd

        response = await self._request(
            "POST",
            "/api/v1/exchanger/questions/ask",
            data=data,
            discord_user_id=user_id
        )
        return response
