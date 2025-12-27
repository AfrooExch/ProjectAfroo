"""
Enums - Status and type definitions matching API
"""

from enum import Enum


class TicketStatus(str, Enum):
    """Ticket status values"""
    CREATED = "created"
    TOS_PENDING = "tos_pending"
    TOS_AGREED = "tos_agreed"
    OPEN = "open"
    CLAIMED = "claimed"
    CLIENT_SENT = "client_sent"
    IN_PROGRESS = "in_progress"
    PAYOUT_PENDING = "payout_pending"
    AWAITING_PAYOUT = "awaiting_payout"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class PayoutMethod(str, Enum):
    """Payout method values"""
    INTERNAL = "internal"
    EXTERNAL = "external"


class SupportTicketType(str, Enum):
    """Support ticket types"""
    GENERAL = "general_question"
    REPORT = "report_exchanger"
    GIVEAWAY = "claim_giveaway"
    BUG = "report_bug"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    FROZEN = "frozen"
    SUSPENDED = "suspended"


class TransactionType(str, Enum):
    """Transaction types"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXCHANGE = "exchange"
    SWAP = "swap"
    FEE = "fee"


class SwapStatus(str, Enum):
    """Swap status values"""
    PENDING = "pending"
    EXCHANGING = "exchanging"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class MilestoneLevel(str, Enum):
    """Customer milestone tiers"""
    BRONZE = "bronze"      # $500
    SILVER = "silver"      # $2,500
    GOLD = "gold"          # $5,000
    PLATINUM = "platinum"  # $10,000
    DIAMOND = "diamond"    # $25,000
    MASTER = "master"      # $50,000


MILESTONE_THRESHOLDS = {
    MilestoneLevel.BRONZE: 500,
    MilestoneLevel.SILVER: 2500,
    MilestoneLevel.GOLD: 5000,
    MilestoneLevel.PLATINUM: 10000,
    MilestoneLevel.DIAMOND: 25000,
    MilestoneLevel.MASTER: 50000,
}
