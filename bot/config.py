"""
Bot Configuration for V4
JSON-based configuration matching V3 structure with V4 enhancements
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import discord
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Configuration manager for Afroo V4 Bot
    Loads from config.json with same structure as V3
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")

    def reload(self):
        """Reload configuration from file"""
        self.load()

    def validate(self):
        """Validate required configuration"""
        # Check environment variables
        required_env = ["DISCORD_TOKEN", "API_BASE_URL", "BOT_SERVICE_TOKEN"]
        missing = [var for var in required_env if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        # Check guild ID
        if not self.guild_id:
            raise ValueError("Guild ID not configured in config.json")

    # ============================================================================
    # ENVIRONMENT VARIABLES (Sensitive Data)
    # ============================================================================

    @property
    def DISCORD_TOKEN(self) -> str:
        """Discord bot token from environment"""
        return os.getenv("DISCORD_TOKEN", "")

    @property
    def API_BASE_URL(self) -> str:
        """API base URL from environment"""
        return os.getenv("API_BASE_URL", "http://localhost:8000")

    @property
    def BOT_SERVICE_TOKEN(self) -> str:
        """Bot service authentication token from environment"""
        return os.getenv("BOT_SERVICE_TOKEN", "")

    @property
    def API_HEADERS(self) -> Dict[str, str]:
        """API headers for bot service authentication"""
        return {
            "Authorization": f"Bearer {self.BOT_SERVICE_TOKEN}",
            "Content-Type": "application/json"
        }

    @property
    def LOG_LEVEL(self) -> str:
        """Logging level from environment"""
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def DEBUG(self) -> bool:
        """Debug mode from environment"""
        return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # ============================================================================
    # GUILD
    # ============================================================================

    @property
    def guild_id(self) -> int:
        """Discord guild/server ID"""
        return self._config["guild"]["id"]

    @property
    def GUILD_ID(self) -> int:
        """Alias for guild_id"""
        return self.guild_id

    @property
    def DISCORD_GUILD_ID(self) -> int:
        """Alias for guild_id (used by main.py)"""
        return self.guild_id

    @property
    def voice_stats_channel(self) -> int:
        """Voice stats channel ID"""
        return self._config["guild"].get("voice_stats_channel", 0)

    # ============================================================================
    # CHANNELS
    # ============================================================================

    @property
    def exchange_channel(self) -> int:
        """Main exchange panel channel"""
        return self._config["channels"]["exchange"]

    @property
    def CHANNEL_EXCHANGE_PANEL(self) -> int:
        """Alias for exchange_channel"""
        return self.exchange_channel

    @property
    def ticket_log_channel(self) -> int:
        """Ticket logging channel"""
        return self._config["channels"]["ticket_log"]

    @property
    def tos_channel(self) -> int:
        """Terms of Service channel"""
        return self._config["channels"]["tos"]

    @property
    def CHANNEL_TOS(self) -> int:
        """Alias for tos_channel"""
        return self.tos_channel

    @property
    def fees_channel(self) -> int:
        """Fees information channel"""
        return self._config["channels"].get("fees", self.tos_channel)

    @property
    def CHANNEL_FEES(self) -> int:
        """Alias for fees_channel"""
        return self.fees_channel

    @property
    def reputation_channel(self) -> int:
        """Reputation/vouches channel"""
        return self._config["channels"].get("reputation", self.tos_channel)

    @property
    def CHANNEL_REPUTATION(self) -> int:
        """Alias for reputation_channel"""
        return self.reputation_channel

    @property
    def CHANNEL_REP(self) -> int:
        """Alias for reputation channel (used by completion notifier)"""
        return self.reputation_channel

    @property
    def exchange_history_channel(self) -> int:
        """Exchange history/transcripts channel"""
        return self._config["channels"]["exchange_history"]

    @property
    def CHANNEL_EXCHANGE_HISTORY(self) -> int:
        """Alias for exchange_history_channel (used by completion notifier)"""
        return self.exchange_history_channel

    @property
    def public_exchange_log_channel(self) -> int:
        """Public exchange log channel"""
        return self._config["channels"].get("public_exchange_log_channel", 0)

    @property
    def admin_panel_channel(self) -> int:
        """Admin panel channel"""
        return self._config["channels"]["admin_panel"]

    @property
    def support_panel_channel(self) -> int:
        """Support panel channel"""
        return self._config["channels"]["support_panel"]

    @property
    def CHANNEL_SUPPORT_PANEL(self) -> int:
        """Alias for support_panel_channel"""
        return self.support_panel_channel

    @property
    def application_panel_channel(self) -> int:
        """Application panel channel"""
        return self._config["channels"]["application_panel"]

    @property
    def CHANNEL_APPLICATION_PANEL(self) -> int:
        """Alias for application_panel_channel"""
        return self.application_panel_channel

    @property
    def user_dashboard_channel(self) -> int:
        """User dashboard panel channel"""
        return self._config["channels"].get("user_dashboard", 0)

    @property
    def CHANNEL_DASHBOARD_PANEL(self) -> int:
        """Alias for user_dashboard_channel"""
        return self.user_dashboard_channel

    @property
    def leaderboard_channel(self) -> int:
        """Leaderboard panel channel"""
        return self._config["channels"].get("leaderboard", 0)

    @property
    def CHANNEL_LEADERBOARD_PANEL(self) -> int:
        """Alias for leaderboard_channel"""
        return self.leaderboard_channel

    @property
    def deposit_panel_channel(self) -> int:
        """Deposit panel channel"""
        return self._config["channels"].get("deposit_panel", 0)

    @property
    def CHANNEL_DEPOSIT_PANEL(self) -> int:
        """Alias for deposit_panel_channel"""
        return self.deposit_panel_channel

    # V4 NEW CHANNELS

    @property
    def swap_panel_channel(self) -> int:
        """Swap panel channel (V4)"""
        return self._config["channels"].get("swap_panel", 0)

    @property
    def CHANNEL_SWAP_PANEL(self) -> int:
        """Alias for swap_panel_channel"""
        return self.swap_panel_channel

    @property
    def wallet_panel_channel(self) -> int:
        """Wallet panel channel (V4)"""
        return self._config["channels"].get("wallet_panel", 0)

    @property
    def CHANNEL_WALLET_PANEL(self) -> int:
        """Alias for wallet_panel_channel"""
        return self.wallet_panel_channel

    @property
    def automm_panel_channel(self) -> int:
        """AutoMM escrow panel channel (V4)"""
        return self._config["channels"].get("automm_panel", 0)

    @property
    def CHANNEL_AUTOMM_PANEL(self) -> int:
        """Alias for automm_panel_channel"""
        return self.automm_panel_channel

    # Utility Channels

    @property
    def welcome_channel(self) -> int:
        """Welcome channel"""
        return self._config["channels"].get("welcome", 0)

    @property
    def website_channel(self) -> int:
        """Website info channel"""
        return self._config["channels"].get("website", 0)

    @property
    def exchanger_panel_channel(self) -> int:
        """Exchanger panel channel"""
        return self._config["channels"].get("exchanger_panel", 0)

    @property
    def exchanger_faq_channel(self) -> int:
        """Exchanger FAQ channel"""
        return self._config["channels"].get("exchanger_faq", 0)

    @property
    def exchanger_rules_channel(self) -> int:
        """Exchanger rules channel"""
        return self._config["channels"].get("exchanger_rules", 0)

    @property
    def exchanger_chat_channel(self) -> int:
        """Exchanger chat channel"""
        return self._config["channels"].get("exchanger_chat", 0)

    @property
    def exch_mod_chat_channel(self) -> int:
        """Exchanger + mod chat channel"""
        return self._config["channels"].get("exch_mod_chat", 0)

    @property
    def admin_chat_channel(self) -> int:
        """Admin chat channel"""
        return self._config["channels"].get("admin_chat", 0)

    @property
    def admin_alerts_channel(self) -> int:
        """Admin alerts channel"""
        return self._config["channels"].get("admin_alerts", 0)

    @property
    def transcript_channel(self) -> int:
        """Transcript storage channel"""
        return self._config["channels"].get("transcript", 0)

    @property
    def member_logs_channel(self) -> int:
        """Member join/leave logs"""
        return self._config["channels"].get("member_logs", 0)

    @property
    def CHANNEL_MEMBER_LOGS(self) -> int:
        """Alias for member_logs_channel"""
        return self.member_logs_channel

    @property
    def message_logs_channel(self) -> int:
        """Message edit/delete logs"""
        return self._config["channels"].get("message_logs", 0)

    @property
    def CHANNEL_MESSAGE_LOGS(self) -> int:
        """Alias for message_logs_channel"""
        return self.message_logs_channel

    @property
    def server_logs_channel(self) -> int:
        """General server logs"""
        return self._config["channels"].get("server_logs", 0)

    @property
    def CHANNEL_SERVER_LOGS(self) -> int:
        """Alias for server_logs_channel"""
        return self.server_logs_channel

    # ============================================================================
    # CATEGORIES
    # ============================================================================

    @property
    def tickets_category(self) -> int:
        """Unclaimed tickets category"""
        return self._config["categories"]["tickets"]

    @property
    def CATEGORY_TICKETS(self) -> int:
        """Alias for tickets_category"""
        return self.tickets_category

    @property
    def CLIENT_TICKETS_CATEGORY_ID(self) -> int:
        """Client tickets category ID (private client channels)"""
        return self.tickets_category

    @property
    def TICKETS_CATEGORY_ID(self) -> int:
        """Alias for CLIENT_TICKETS_CATEGORY_ID (backwards compatibility)"""
        return self.CLIENT_TICKETS_CATEGORY_ID

    @property
    def EXCHANGER_TICKETS_CATEGORY_ID(self) -> int:
        """Exchanger tickets category ID (view-only for payment-specific exchangers)"""
        return self._config["categories"].get("exchanger_tickets", 0)

    @property
    def claimed_tickets_category(self) -> int:
        """Claimed/active tickets category"""
        return self._config["categories"]["claimed_tickets"]

    @property
    def CLAIMED_TICKETS_CATEGORY_ID(self) -> int:
        """Claimed tickets category ID (moved here after claim)"""
        return self.claimed_tickets_category

    @property
    def CATEGORY_CLAIMED_TICKETS(self) -> int:
        """Alias for claimed_tickets_category"""
        return self.claimed_tickets_category

    @property
    def support_tickets_category(self) -> int:
        """Support tickets category"""
        return self._config["categories"]["support_tickets"]

    @property
    def support_category(self) -> int:
        """Alias for support_tickets_category"""
        return self.support_tickets_category

    @property
    def CATEGORY_SUPPORT(self) -> int:
        """Alias for support_tickets_category"""
        return self.support_tickets_category

    @property
    def applications_category(self) -> int:
        """Exchanger applications category"""
        return self._config["categories"].get("exchanger_applications", 0)

    @property
    def CATEGORY_APPLICATIONS(self) -> int:
        """Alias for applications_category"""
        return self.applications_category

    # V4 NEW CATEGORIES

    @property
    def swaps_category(self) -> int:
        """Swaps category (V4)"""
        return self._config["categories"].get("swaps", 0)

    # V4 FORUM CHANNELS (Thread-based tickets)

    @property
    def FORUM_CLIENT_TICKETS(self) -> int:
        """Client tickets forum channel ID (V4)"""
        return self._config["categories"].get("forum_client_tickets", 1450701785655279666)

    @property
    def FORUM_EXCHANGER_QUEUE(self) -> int:
        """Exchanger queue forum channel ID (V4)"""
        return self._config["categories"].get("forum_exchanger_queue", 1450701390107246703)

    @property
    def CATEGORY_SWAPS(self) -> int:
        """Alias for swaps_category"""
        return self.swaps_category

    @property
    def escrow_category(self) -> int:
        """AutoMM escrow category (V4)"""
        return self._config["categories"].get("escrow", 0)

    @property
    def CATEGORY_ESCROW(self) -> int:
        """Alias for escrow_category"""
        return self.escrow_category

    # Archive Categories

    @property
    def archived_support_category(self) -> int:
        """Archived support tickets"""
        return self._config["categories"].get("archived_support", 0)

    @property
    def archived_tickets_category(self) -> int:
        """Archived exchange tickets"""
        return self._config["categories"].get("archived_tickets", 0)

    # ============================================================================
    # ROLES
    # ============================================================================

    @property
    def exchanger_role(self) -> int:
        """Exchanger role"""
        return self._config["roles"]["exchanger"]

    @property
    def ROLE_EXCHANGER(self) -> int:
        """Alias for exchanger_role"""
        return self.exchanger_role

    @property
    def staff_role(self) -> int:
        """Staff role"""
        return self._config["roles"]["staff"]

    @property
    def ROLE_STAFF(self) -> int:
        """Alias for staff_role"""
        return self.staff_role

    @property
    def head_admin_role(self) -> int:
        """Head admin role"""
        return self._config["roles"].get("head_admin", 0)

    @property
    def ROLE_ADMIN(self) -> int:
        """Alias for head_admin_role"""
        return self.head_admin_role

    @property
    def assistant_admin_role(self) -> int:
        """Assistant admin role"""
        return self._config["roles"].get("assistant_admin", 0)

    @property
    def ROLE_ASSISTANT_ADMIN(self) -> int:
        """Alias for assistant_admin_role"""
        return self.assistant_admin_role

    @property
    def customer_role(self) -> int:
        """Customer role"""
        return self._config["roles"].get("customer", 0)

    @property
    def ROLE_CUSTOMER(self) -> int:
        """Alias for customer_role"""
        return self.customer_role

    # Exchanger Limit Roles

    @property
    def exchanger_limit_100_role(self) -> int:
        """Exchanger $100 limit role"""
        return self._config["roles"].get("exchanger_limit_100", 0)

    @property
    def exchanger_limit_250_role(self) -> int:
        """Exchanger $250 limit role"""
        return self._config["roles"].get("exchanger_limit_250", 0)

    @property
    def exchanger_unlimited_role(self) -> int:
        """Exchanger unlimited role"""
        return self._config["roles"].get("exchanger_unlimited", 0)

    # Payment Method Exchanger Roles

    @property
    def exchanger_paypal_role(self) -> int:
        """PayPal exchanger role"""
        return self._config["roles"].get("exchanger_paypal", 0)

    @property
    def exchanger_cashapp_role(self) -> int:
        """CashApp exchanger role"""
        return self._config["roles"].get("exchanger_cashapp", 0)

    @property
    def exchanger_applepay_role(self) -> int:
        """ApplePay exchanger role"""
        return self._config["roles"].get("exchanger_applepay", 0)

    @property
    def exchanger_venmo_role(self) -> int:
        """Venmo exchanger role"""
        return self._config["roles"].get("exchanger_venmo", 0)

    @property
    def exchanger_zelle_role(self) -> int:
        """Zelle exchanger role"""
        return self._config["roles"].get("exchanger_zelle", 0)

    @property
    def exchanger_chime_role(self) -> int:
        """Chime exchanger role"""
        return self._config["roles"].get("exchanger_chime", 0)

    @property
    def exchanger_revolut_role(self) -> int:
        """Revolut exchanger role"""
        return self._config["roles"].get("exchanger_revolut", 0)

    @property
    def exchanger_skrill_role(self) -> int:
        """Skrill exchanger role"""
        return self._config["roles"].get("exchanger_skrill", 0)

    @property
    def exchanger_bank_role(self) -> int:
        """Bank exchanger role"""
        return self._config["roles"].get("exchanger_bank", 0)

    @property
    def exchanger_paysafe_role(self) -> int:
        """PaySafe exchanger role"""
        return self._config["roles"].get("exchanger_paysafe", 0)

    @property
    def exchanger_binance_gift_card_role(self) -> int:
        """Binance Gift Card exchanger role"""
        return self._config["roles"].get("exchanger_binance_gift_card", 0)

    @property
    def exchanger_crypto_role(self) -> int:
        """Crypto exchanger role"""
        return self._config["roles"].get("exchanger_crypto", 0)

    def get_exchanger_roles_for_methods(self, send_method: str, receive_method: str) -> list[int]:
        """
        Get appropriate exchanger roles for payment methods

        Rules:
        - Fiat to Fiat (CashApp → PayPal): Ping CashApp AND PayPal, NOT All Exchangers
        - Fiat to Crypto (CashApp → Crypto): Ping ONLY CashApp (the fiat side)
        - Crypto to Fiat (Crypto → CashApp): Ping ONLY CashApp (the fiat side)
        - Crypto to Crypto: Ping All Exchangers only
        """
        roles = set()

        # Map payment methods to their specific roles
        # Note: Payment method IDs may have _balance suffix, so we normalize them
        method_role_map = {
            "paypal": self.exchanger_paypal_role,
            "paypal_balance": self.exchanger_paypal_role,
            "cashapp": self.exchanger_cashapp_role,
            "cashapp_balance": self.exchanger_cashapp_role,
            "applepay": self.exchanger_applepay_role,
            "applepay_balance": self.exchanger_applepay_role,
            "venmo": self.exchanger_venmo_role,
            "venmo_balance": self.exchanger_venmo_role,
            "zelle": self.exchanger_zelle_role,
            "zelle_balance": self.exchanger_zelle_role,
            "chime": self.exchanger_chime_role,
            "chime_balance": self.exchanger_chime_role,
            "revolut": self.exchanger_revolut_role,
            "revolut_balance": self.exchanger_revolut_role,
            "skrill": self.exchanger_skrill_role,
            "skrill_balance": self.exchanger_skrill_role,
            "bank": self.exchanger_bank_role,
            "bank_transfer": self.exchanger_bank_role,
            "paysafe": self.exchanger_paysafe_role,
            "paysafecard": self.exchanger_paysafe_role,
            "binance_gift_card": self.exchanger_binance_gift_card_role,
            "crypto": self.exchanger_crypto_role
        }

        # Determine if methods are crypto or fiat
        is_send_crypto = send_method == "crypto"
        is_receive_crypto = receive_method == "crypto"

        # Case 1: Crypto to Crypto - ping all exchangers ONLY
        if is_send_crypto and is_receive_crypto:
            roles.add(self.ROLE_EXCHANGER)
        # Case 2: Fiat to Crypto - ping ONLY the fiat role (send side)
        elif not is_send_crypto and is_receive_crypto:
            if send_method in method_role_map and method_role_map[send_method]:
                roles.add(method_role_map[send_method])
        # Case 3: Crypto to Fiat - ping ONLY the fiat role (receive side)
        elif is_send_crypto and not is_receive_crypto:
            if receive_method in method_role_map and method_role_map[receive_method]:
                roles.add(method_role_map[receive_method])
        # Case 4: Fiat to Fiat - ping BOTH fiat roles (NOT all exchangers)
        else:
            for method in [send_method, receive_method]:
                if method in method_role_map and method_role_map[method]:
                    roles.add(method_role_map[method])

        # If no specific roles found, use generic exchanger role as fallback
        if not roles:
            roles.add(self.ROLE_EXCHANGER)

        return list(roles)

    # Milestone Roles

    @property
    def milestone_roles(self) -> Dict[int, int]:
        """All milestone roles"""
        return {int(k): v for k, v in self._config["roles"].get("milestone_roles", {}).items()}

    @property
    def milestone_500_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("500", 0)

    @property
    def milestone_1500_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("1500", 0)

    @property
    def milestone_2500_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("2500", 0)

    @property
    def milestone_5000_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("5000", 0)

    @property
    def milestone_10000_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("10000", 0)

    @property
    def milestone_25000_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("25000", 0)

    @property
    def milestone_50000_role(self) -> int:
        return self._config["roles"].get("milestone_roles", {}).get("50000", 0)

    # ============================================================================
    # EMOJI
    # ============================================================================

    @property
    def emoji_names(self) -> Dict[str, str]:
        """Custom emoji names"""
        return self._config.get("emoji_names", {})

    def get_emojis(self, bot) -> Dict[str, str]:
        """Get custom server emojis or fallback to unicode"""
        import logging
        logger = logging.getLogger(__name__)

        emoji_map = {}

        if not bot:
            logger.warning("No bot instance provided, using fallback emojis")
            return self._get_fallback_emojis()

        guild = bot.get_guild(self.guild_id)

        if not guild:
            logger.error(f"Guild not found with ID: {self.guild_id}, using fallback emojis")
            return self._get_fallback_emojis()

        emoji_config = self._config.get("emoji_names", {})

        for payment_method, emoji_name in emoji_config.items():
            emoji = discord.utils.get(guild.emojis, name=emoji_name)
            if emoji:
                emoji_map[payment_method] = str(emoji)
                logger.debug(f"Found emoji '{emoji_name}' for '{payment_method}'")
            else:
                emoji_map[payment_method] = self._get_fallback_emoji(payment_method)
                logger.warning(f"Emoji '{emoji_name}' not found for '{payment_method}', using fallback")

        return emoji_map

    def _get_fallback_emojis(self) -> Dict[str, str]:
        """Unicode fallback emojis"""
        return {
            "bitcoin": "₿", "btc": "₿",
            "litecoin": "Ł", "ltc": "Ł",
            "ethereum": "Ξ", "eth": "Ξ",
            "solana": "◎", "sol": "◎",
            "tether": "₮", "usdt": "₮",
            "usdc": "$",
            "crypto": "🌐",
            "paypal": "💳",
            "cashapp": "💵",
            "venmo": "🔵",
            "zelle": "🟣",
            "amazon": "🛒",
            "card": "💳",
            "bank": "🏦"
        }

    def _get_fallback_emoji(self, payment_method: str) -> str:
        """Get single fallback emoji"""
        fallbacks = self._get_fallback_emojis()
        return fallbacks.get(payment_method, "")

    def get_emoji(self, bot, name: str) -> str:
        """Get single emoji"""
        emojis = self.get_emojis(bot)
        return emojis.get(name, "❓")

    # ============================================================================
    # DEPOSITS
    # ============================================================================

    @property
    def assets_enabled(self) -> List[str]:
        """Enabled deposit assets"""
        return self._config.get("deposits", {}).get("assets_enabled", [])

    @property
    def claim_limit_multiplier(self) -> float:
        """Claim limit multiplier (how much of balance can be used)"""
        return self._config.get("deposits", {}).get("claim_limit_multiplier", 0.8)

    @property
    def hold_multiplier(self) -> float:
        """Hold multiplier for ticket claims"""
        return self._config.get("deposits", {}).get("hold_multiplier", 1.0)

    def get_asset_config(self, asset: str) -> Dict[str, Any]:
        """Get configuration for specific asset"""
        return self._config.get("deposits", {}).get(asset, {})

    def get_asset_network(self, asset: str) -> str:
        """Get network for asset"""
        return self.get_asset_config(asset).get("network", "mainnet")

    def get_asset_min_confirmations(self, asset: str) -> int:
        """Get minimum confirmations for asset"""
        return self.get_asset_config(asset).get("min_confirmations", 1)

    def get_owner_wallet(self, asset: str) -> str:
        """Get owner wallet for fee collection"""
        return self._config.get("deposits", {}).get("owner_wallets", {}).get(asset, "")

    # ============================================================================
    # FEES
    # ============================================================================

    @property
    def fees_rate(self) -> float:
        """Base fees rate"""
        return self._config.get("fees", {}).get("rate", 0.02)

    @property
    def owner_fee_percentage(self) -> float:
        """Owner fee percentage"""
        return self._config.get("fees", {}).get("owner_percentage_of_exchange_amount", 0.02)

    @property
    def min_owner_fee_usd(self) -> float:
        """Minimum owner fee in USD"""
        return self._config.get("fees", {}).get("min_owner_fee_usd", 0.50)

    # ============================================================================
    # SECURITY
    # ============================================================================

    @property
    def allow_key_reveal(self) -> bool:
        """Allow private key reveal"""
        return self._config.get("security", {}).get("allow_key_reveal", False)

    @property
    def key_reveal_window_seconds(self) -> int:
        """Key reveal window in seconds"""
        return self._config.get("security", {}).get("key_reveal_window_seconds", 300)

    # ============================================================================
    # WEBHOOKS
    # ============================================================================

    @property
    def discord_webhook_tickets(self) -> str:
        """Tickets webhook URL"""
        return self._config.get("discord", {}).get("webhooks", {}).get("tickets", "")

    @property
    def discord_webhook_deposits(self) -> str:
        """Deposits webhook URL"""
        return self._config.get("discord", {}).get("webhooks", {}).get("deposits", "")

    @property
    def discord_webhook_system(self) -> str:
        """System webhook URL"""
        return self._config.get("discord", {}).get("webhooks", {}).get("system", "")

    # ============================================================================
    # AUTOMM (V4)
    # ============================================================================

    @property
    def automm_enabled(self) -> bool:
        """Is AutoMM enabled"""
        return self._config.get("automm", {}).get("enabled", True)

    @property
    def automm_assets(self) -> List[str]:
        """AutoMM supported assets"""
        return self._config.get("automm", {}).get("assets", ["LTC", "BTC", "SOL"])

    # ============================================================================
    # TRANSCRIPTS
    # ============================================================================

    @property
    def transcript_enabled(self) -> bool:
        """Are transcripts enabled"""
        return self._config.get("transcripts", {}).get("enabled", True)

    @property
    def transcript_base_url(self) -> str:
        """Transcript service base URL"""
        return self._config.get("transcripts", {}).get("base_url", "https://transcripts.afrooexch.com")

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    @property
    def admin_users(self) -> List[int]:
        """List of admin user IDs from environment"""
        admins_str = os.getenv("ADMINS", "")
        if not admins_str:
            return []
        try:
            return [int(admin_id.strip()) for admin_id in admins_str.split(",") if admin_id.strip()]
        except ValueError:
            return []

    def is_admin(self, user) -> bool:
        """Check if user is admin (by role or ID)"""
        if hasattr(user, 'id'):
            if user.id in self.admin_users:
                return True

        if hasattr(user, 'roles'):
            role_ids = {role.id for role in user.roles}
            return self.head_admin_role in role_ids or self.staff_role in role_ids

        return False

    @classmethod
    def is_staff(cls, user) -> bool:
        """Check if user has staff role"""
        if hasattr(user, 'roles'):
            role_ids = {role.id for role in user.roles}
            return cls.ROLE_STAFF in role_ids or cls.ROLE_ADMIN in role_ids
        return False

    @classmethod
    def is_exchanger(cls, user) -> bool:
        """Check if user has exchanger role"""
        if hasattr(user, 'roles'):
            role_ids = {role.id for role in user.roles}
            return cls.ROLE_EXCHANGER in role_ids
        return False


# Global config instance
config = Config()

# Module-level exports for direct imports
API_BASE_URL = config.API_BASE_URL
API_HEADERS = config.API_HEADERS
