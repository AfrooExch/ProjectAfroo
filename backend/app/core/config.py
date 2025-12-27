"""
Application configuration using Pydantic Settings
All configuration values loaded from environment variables
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings - All values from environment"""

    # Application
    APP_NAME: str
    VERSION: str
    ENVIRONMENT: str
    DEBUG: bool
    LOG_LEVEL: str

    # Database
    MONGODB_URL: str
    DATABASE_NAME: str

    # Redis
    REDIS_URL: str
    REDIS_PASSWORD: str

    # Security
    ENCRYPTION_KEY: str  # Fernet key for private key encryption
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # Discord OAuth2
    DISCORD_CLIENT_ID: str
    DISCORD_CLIENT_SECRET: str
    DISCORD_REDIRECT_URI: str
    DISCORD_BOT_TOKEN: str
    DISCORD_API_ENDPOINT: str
    DISCORD_GUILD_ID: int

    # Admin User IDs (Personal Discord accounts with admin access)
    DISCORD_HEAD_ADMIN_USER_ID: int
    DISCORD_ASSISTANT_ADMIN_USER_ID: int

    # Discord Roles (for permission validation)
    ROLE_HEAD_ADMIN: int
    ROLE_ASSISTANT_ADMIN: int
    ROLE_STAFF: int
    ROLE_EXCHANGER: int
    ROLE_CUSTOMER: int

    # Customer Tier Role IDs (for tier sync system)
    TIER_ROLE_LEGEND: int
    TIER_ROLE_ELITE: int
    TIER_ROLE_DIAMOND: int
    TIER_ROLE_PLATINUM: int
    TIER_ROLE_GOLD: int
    TIER_ROLE_SILVER: int
    TIER_ROLE_BRONZE: int

    # Bot Service
    BOT_SERVICE_TOKEN: str

    # Blockchain (Tatum)
    TATUM_API_KEY: str
    TATUM_API_URL: str
    TATUM_WEBHOOK_SECRET: str
    TATUM_WEBHOOK_BASE_URL: str

    # Wallet System
    SERVER_PROFIT_RATE: float
    MIN_PROFIT_USD: float
    PROFIT_BATCH_THRESHOLD_USD: float
    WITHDRAWAL_MIN_USD: float
    WITHDRAWAL_MAX_USD: float
    LARGE_WITHDRAWAL_THRESHOLD_USD: float

    # Admin Wallets
    ADMIN_WALLET_BTC: str
    ADMIN_WALLET_LTC: str
    ADMIN_WALLET_ETH: str
    ADMIN_WALLET_SOL: str
    ADMIN_WALLET_USDC_SOL: str
    ADMIN_WALLET_USDC_ETH: str
    ADMIN_WALLET_USDT_SOL: str
    ADMIN_WALLET_USDT_ETH: str
    ADMIN_WALLET_XRP: str
    ADMIN_WALLET_BNB: str
    ADMIN_WALLET_TRX: str
    ADMIN_WALLET_MATIC: str
    ADMIN_WALLET_AVAX: str
    ADMIN_WALLET_DOGE: str

    # Swap Provider (ChangeNow)
    CHANGENOW_API_KEY: str

    # AI (OpenAI)
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    OPENAI_MAX_TOKENS: int
    OPENAI_TEMPERATURE: float

    # Notifications
    # Note: Email notifications are DISABLED
    # Only Discord DM and website notifications are used

    # CORS (comma-separated origins)
    CORS_ORIGINS: str

    # API Settings
    API_V1_PREFIX: str
    PROJECT_NAME: str
    PUBLIC_URL: str  # Public URL for transcript links

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int
    RATE_LIMIT_WALLET_OPS: int
    RATE_LIMIT_EXCHANGE_CREATE: int

    # File Uploads
    MAX_UPLOAD_SIZE_MB: int
    ALLOWED_FILE_TYPES: str

    # Monitoring
    SENTRY_DSN: str
    SENTRY_ENVIRONMENT: str

    # Feature Flags
    FEATURE_AI_ENABLED: bool
    FEATURE_SWAPS_ENABLED: bool
    FEATURE_WITHDRAWALS_ENABLED: bool

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    def get_admin_wallet(self, currency: str) -> str:
        """
        Get admin wallet address for a specific currency

        Args:
            currency: Currency code (BTC, ETH, USDC-SOL, etc.)

        Returns:
            Admin wallet address for that currency
        """
        currency_upper = currency.upper().replace("-", "_")
        wallet_attr = f"ADMIN_WALLET_{currency_upper}"

        wallet = getattr(self, wallet_attr, None)

        if not wallet or wallet.startswith("DAdmin"):  # Placeholder check
            raise ValueError(f"Admin wallet not configured for {currency}")

        return wallet

    def get_tier_role_ids(self) -> dict:
        """
        Get all tier role IDs as a dictionary

        Returns:
            Dict mapping tier names to Discord role IDs
        """
        return {
            'Legend': self.TIER_ROLE_LEGEND,
            'Elite': self.TIER_ROLE_ELITE,
            'Diamond': self.TIER_ROLE_DIAMOND,
            'Platinum': self.TIER_ROLE_PLATINUM,
            'Gold': self.TIER_ROLE_GOLD,
            'Silver': self.TIER_ROLE_SILVER,
            'Bronze': self.TIER_ROLE_BRONZE,
        }


# Create settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings
