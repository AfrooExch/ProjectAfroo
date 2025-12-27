"""
AFROO Exchange AI - Autonomous Community Assistant
- Progressive timeout system for violations
- Autonomous TOS enforcement
- Community engagement
- Link/image moderation
- Never reveals AI provider
"""

import discord
from discord.ext import commands, tasks
import os
import logging
import aiohttp
import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Dict
from bs4 import BeautifulSoup
import re
from collections import defaultdict

try:
    import anthropic
    AI_PROVIDER = "claude"
except ImportError:
    AI_PROVIDER = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('afroo_ai.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
TOKEN = os.getenv("AI_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SERVER_ID = int(os.getenv("DISCORD_SERVER_ID", "0"))
ADMIN_ROLE_IDS = [int(x) for x in os.getenv("ADMIN_ROLE_IDS", "").split(",") if x]
GENERAL_CHAT_ID = int(os.getenv("GENERAL_CHAT_ID", "0"))
EXCHANGER_CHAT_ID = int(os.getenv("EXCHANGER_CHAT_ID", "0"))
TICKET_CATEGORY_IDS = [int(x) for x in os.getenv("TICKET_CATEGORY_IDS", "").split(",") if x]
TOS_URL = os.getenv("TOS_URL", "https://afrooexch.com/tos")

# Moderation settings
BAD_WORDS = [
    "fuck", "shit", "bitch", "asshole", "damn", "cunt", "dick", "pussy",
    "nigger", "nigga", "fag", "faggot", "retard", "retarded",
    "scam", "scammer", "hack", "hacker", "steal", "fraud", "fake"
]

ALLOWED_LINK_PATTERNS = [
    r'afrooexch(?:ange)?\.com',
    r'discord\.gg/afrooexch'
]

# Violation tracking: user_id -> [violation_timestamps]
violation_tracker: Dict[int, list] = defaultdict(list)

# Community engagement settings
ENGAGEMENT_CHANCE = 0.02  # 2% chance to engage in casual chat
LAST_ENGAGEMENT = None
MIN_ENGAGEMENT_INTERVAL = 600  # 10 minutes between engagements

# Create bot
intents = discord.Intents.all()  # Need all intents for timeouts
bot = commands.Bot(command_prefix="!", intents=intents)

# AI client
if AI_PROVIDER == "claude" and ANTHROPIC_API_KEY:
    ai_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    AI_MODEL = "claude-sonnet-4-5"  # Latest Claude 4.5 Sonnet
else:
    ai_client = None
    logger.error("Claude API not configured!")

# TOS context storage
TOS_CONTEXT = ""
LAST_TOS_FETCH = None
NEXT_PURGE_TIME = None


# ====================
# Utility Functions
# ====================

def is_admin(member: discord.Member) -> bool:
    """Check if user is admin"""
    if not member:
        return False
    return any(role.id in ADMIN_ROLE_IDS for role in member.roles)


def clean_violation_history(user_id: int):
    """Remove violations older than 30 days"""
    if user_id not in violation_tracker:
        return

    cutoff = datetime.now() - timedelta(days=30)
    violation_tracker[user_id] = [
        v for v in violation_tracker[user_id]
        if v > cutoff
    ]


def get_timeout_duration(user_id: int) -> timedelta:
    """
    Get timeout duration based on violation count
    1st: 10 minutes
    2nd: 1 hour
    3rd+: 1 day
    """
    clean_violation_history(user_id)

    violation_count = len(violation_tracker[user_id])

    if violation_count == 0:
        return timedelta(minutes=10)
    elif violation_count == 1:
        return timedelta(hours=1)
    else:
        return timedelta(days=1)


async def apply_timeout(member: discord.Member, duration: timedelta, reason: str):
    """Apply timeout to member"""
    try:
        await member.timeout(duration, reason=reason)

        # Track violation
        violation_tracker[member.id].append(datetime.now())

        violation_num = len(violation_tracker[member.id])

        logger.warning(f"Timed out {member.name} for {duration} - Violation #{violation_num}: {reason}")

        # DM user
        try:
            embed = discord.Embed(
                title="You've been timed out",
                description=f"**Reason:** {reason}\n**Duration:** {duration}\n**Violation:** #{violation_num}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="📜 Reminder",
                value="Please follow server rules. Repeated violations result in longer timeouts.",
                inline=False
            )
            embed.set_footer(text="Afroo Exchange AI")
            await member.send(embed=embed)
        except:
            pass

        return True

    except discord.Forbidden:
        logger.error(f"Missing permissions to timeout {member.name}")
        return False


# ====================
# TOS Fetching
# ====================

async def fetch_tos_from_website() -> str:
    """Fetch TOS from website"""
    global TOS_CONTEXT, LAST_TOS_FETCH

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TOS_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    tos_content = soup.get_text(strip=True, separator='\n')
                    TOS_CONTEXT = tos_content[:10000]
                    LAST_TOS_FETCH = datetime.now()
                    logger.info(f"Fetched TOS ({len(TOS_CONTEXT)} chars)")
                    return TOS_CONTEXT

    except Exception as e:
        logger.error(f"Error fetching TOS: {e}")

    return ""


async def ensure_tos_loaded():
    """Ensure TOS is fresh"""
    global TOS_CONTEXT, LAST_TOS_FETCH

    if not TOS_CONTEXT or not LAST_TOS_FETCH or \
       (datetime.now() - LAST_TOS_FETCH) > timedelta(hours=6):
        await fetch_tos_from_website()


# ====================
# AI Response Generation
# ====================

async def get_ai_response(
    user_message: str,
    context: str = "",
    personality: str = "helpful"
) -> str:
    """Get AI response - NEVER reveals it's Claude"""

    if not ai_client:
        return "I'm currently unavailable. Please try again later."

    # Build system prompt with STRICT identity rules
    if personality == "casual":
        system_prompt = f"""You are the Afroo Exchange AI, the official AI assistant for Afroo Exchange cryptocurrency platform.

CRITICAL IDENTITY RULES:
- You ARE "Afroo Exchange AI" or just "Afroo AI"
- NEVER mention Claude, Anthropic, OpenAI, GPT, or any AI provider
- If asked what AI you are, say "I'm the Afroo Exchange AI assistant"
- You were built specifically for Afroo Exchange

Your personality:
- Friendly and casual (but professional)
- Helpful community member
- Knowledgeable about crypto and exchanges
- Keep responses SHORT (1-2 sentences for casual chat)

TOS Context:
{TOS_CONTEXT[:3000] if TOS_CONTEXT else "TOS not loaded"}

{context}
"""
    else:
        system_prompt = f"""You are the Afroo Exchange AI, the official AI assistant for Afroo Exchange cryptocurrency platform.

CRITICAL IDENTITY RULES:
- You ARE "Afroo Exchange AI" - this is your identity
- NEVER mention Claude, Anthropic, OpenAI, GPT, or any other AI provider
- If asked what model/AI you use, say "I'm a custom AI built for Afroo Exchange"
- You were designed specifically for this platform

Your role:
- Answer questions concisely and accurately
- Keep responses SHORT (2-3 sentences max)
- Be helpful but brief
- Only respond to DIRECT questions

CRITICAL TOS RULE:
EXCHANGES MUST ONLY HAPPEN IN TICKETS - NEVER IN DMS!

COMMON Q&A (answer these quickly):

Q: How do I claim a ticket?
A: Go to Exchanger Panel and deposit funds. It's 1:1 ratio - $50 deposited = claim $50 tickets. Then click the claim button in the ticket.

Q: What are the server fees?
A: Minimum 50 cents per ticket, or 2% of ticket total if over $0.50.

Q: Do I have to deposit to claim tickets?
A: Yes, everyone except ADMINS must deposit to claim tickets.

PLATFORM KNOWLEDGE:

Client Fees:
- Minimum fee: $4 on all exchanges
- Under $40: Flat $4 fee
- Over $40: 10% fee
- Crypto to Crypto: 5% fee (any amount)
- Wallet transactions: 0.2% fee
- Swaps: 0.4% fee
- Fees can be negotiated with your exchanger
- Card payments have higher fees due to chargeback risk

Examples:
- $30 exchange → $4 fee → $26 received
- $100 exchange → $10 fee → $90 received
- $100 crypto/crypto → $5 fee → $95 received

Exchanger Fees:
- Server takes minimum 50 cents per ticket, or 2% if over $0.50
- Auto-withdrawn from your deposit

Exchanger Panel Features:
- Deposits: Supports 14 different coins
- My Balance & Holds: View balance, held funds in tickets, and fees owed
- Withdraw: Withdraw unheld funds
- History: View wallet history and on-chain data
- Refresh: Rechecks wallets and holds with latest blockchain data
- Ask Questions: Ask questions to tickets without claiming
- Role Preference: Pick roles to only get notified for exchanges you can do

Services Offered:
- P2P Exchanges
- Crypto to Crypto auto swap
- AutoMM: Securely use Afroo bot to middleman crypto in transactions
- Afroo Wallet: Web and Discord-based wallet with 14 coins, no KYC
- User Dashboard: Generate recovery codes for your account and data

Trust Levels:
- Assistant Admins: Trusted, but never exchange more than their nickname says without claim
- 100% Trusted: ONLY Afroo and Sklaps

Supported Cryptocurrencies (14 total):
- LTC, BTC, ETH, SOL, USDC-SOL, USDC-ETH, USDT-SOL, USDT-TRX, XRP, BNB, TRX, MATIC, AVAX, DOGE

Accepted Payment Methods:
- Crypto, PayPal, Cashapp, ApplePay, Venmo, Zelle, Chime, Revolut, Skrill, Bank Transfer/Wire, PaySafe, Binance Giftcard

Exchange Timing:
- Popular methods (PayPal, Cashapp, Zelle, Revolut) during normal hours: ~5 minutes
- Exchangers have lives - be patient if they're offline

Disputes:
- First try to work it out between exchanger and client
- If unresolved, ping AfrooExchAdmin for final verdict
- AfrooExchAdmin can issue refunds at any time

Exchange Limits:
- Minimum: $4.1 (because minimum fee is $4)
- Maximum: No hard limit, but larger transfers take time
- Risky payment methods (like cards) may be ignored due to chargeback risk

Useful Discord Channels:
- Support Tickets: https://discord.com/channels/1381858031830302791/1411547608215847022
- Exchanger Applications: https://discord.com/channels/1381858031830302791/1387457890595508267
- Exchange: https://discord.com/channels/1381858031830302791/1411701078700855336
- Swap: https://discord.com/channels/1381858031830302791/1439394338827403488
- AutoMM: https://discord.com/channels/1381858031830302791/1439394383043760260
- Afroo Wallet: https://discord.com/channels/1381858031830302791/1439394441294118922
- User Dashboard: https://discord.com/channels/1381858031830302791/1431344634088656926
- Exchanger Panel: https://discord.com/channels/1381858031830302791/1411547365973692456

TOS Context:
{TOS_CONTEXT[:3000] if TOS_CONTEXT else "TOS not loaded"}

{context}
"""

    try:
        response = await ai_client.messages.create(
            model=AI_MODEL,
            max_tokens=400 if personality == "casual" else 500,  # Shorter responses
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        return response.content[0].text

    except Exception as e:
        logger.error(f"AI error: {e}")
        return "I'm having trouble responding right now. Please try again."


# ====================
# Moderation Functions
# ====================

async def moderate_message(message: discord.Message) -> tuple[bool, str]:
    """
    Check if message violates rules
    Returns: (should_delete, should_timeout, reason)
    """

    # Admins bypass all restrictions
    if is_admin(message.author):
        return False, False, ""

    content_lower = message.content.lower()

    # Check bad words
    for word in BAD_WORDS:
        if word in content_lower:
            return True, True, f"Inappropriate language: {word}"

    # Check for DM exchange mentions (CRITICAL)
    dm_keywords = ["dm me", "message me", "pm me", "dms open", "dm for", "text me"]
    if any(keyword in content_lower for keyword in dm_keywords):
        if any(word in content_lower for word in ["exchange", "trade", "sell", "buy", "crypto"]):
            return True, True, "EXCHANGES MUST ONLY HAPPEN IN TICKETS - NEVER DMS (You will get scammed!)"

    # Check links
    links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
    if links:
        for link in links:
            # Check if link is allowed
            is_allowed = any(re.search(pattern, link, re.IGNORECASE) for pattern in ALLOWED_LINK_PATTERNS)
            if not is_allowed:
                return True, False, "Unauthorized link"

    # Check for images/attachments
    if message.attachments:
        return True, False, "Unauthorized attachment"

    return False, False, ""


# ====================
# Event Handlers
# ====================

@bot.event
async def on_ready():
    """Bot startup"""
    logger.info(f"Afroo Exchange AI connected as {bot.user}")
    logger.info(f"Connected to {len(bot.guilds)} guilds")

    # Fetch TOS
    await fetch_tos_from_website()

    # Start background tasks
    if GENERAL_CHAT_ID:
        purge_general_chat.start()

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for questions and TOS violations"
        )
    )

    logger.info("🤖 Afroo Exchange AI is ready!")


@bot.event
async def on_message(message: discord.Message):
    """Handle all messages - autonomous monitoring"""

    # Ignore bot messages
    if message.author.bot:
        return

    # Ensure TOS is loaded
    await ensure_tos_loaded()

    member = message.author if isinstance(message.author, discord.Member) else None

    # ====================
    # Moderation (ONLY General Chat)
    # ====================
    if member and not is_admin(member) and message.channel.id == GENERAL_CHAT_ID:
        should_delete, should_timeout, reason = await moderate_message(message)

        if should_delete:
            try:
                await message.delete()
                logger.warning(f"Deleted message from {message.author} in General: {reason}")

                if should_timeout:
                    duration = get_timeout_duration(member.id)
                    await apply_timeout(member, duration, reason)

            except discord.Forbidden:
                logger.error("Missing permissions to moderate")

    # ====================
    # Community Engagement (Random)
    # ====================
    global LAST_ENGAGEMENT

    if message.channel.id == GENERAL_CHAT_ID and not is_admin(member):
        # Small chance to engage casually
        time_since_last = (datetime.now() - LAST_ENGAGEMENT).total_seconds() if LAST_ENGAGEMENT else 999999

        if time_since_last > MIN_ENGAGEMENT_INTERVAL and random.random() < ENGAGEMENT_CHANCE:
            try:
                async with message.channel.typing():
                    response = await get_ai_response(
                        f"Someone in community chat said: '{message.content[:200]}'. Reply casually and briefly (1-2 sentences).",
                        "Be friendly and casual, like a helpful community member.",
                        personality="casual"
                    )

                    await message.reply(response)
                    LAST_ENGAGEMENT = datetime.now()
                    logger.info(f"Engaged casually in General Chat")

            except Exception as e:
                logger.error(f"Error in community engagement: {e}")

    # ====================
    # Autonomous AI Responses
    # ====================
    should_respond, context_type = await should_respond_to_message(message)

    if should_respond:
        try:
            async with message.channel.typing():
                # Build context
                if context_type.startswith("exchanger"):
                    context = """Provide helpful information about:
- Ticket processes and claiming
- TOS and policies
- Best practices
Be professional and concise."""

                elif context_type.startswith("ticket"):
                    context = f"""This is ticket: {message.channel.name}
Help both parties understand the exchange process.
Remind them: EXCHANGES ONLY IN TICKETS - NEVER DMS!
Stay neutral and helpful."""

                else:
                    context = "Provide helpful information."

                response = await get_ai_response(message.content, context)
                await message.reply(response)
                logger.info(f"AI responded in {message.channel.name} ({context_type})")

        except Exception as e:
            logger.error(f"Error generating response: {e}")

    # ====================
    # TOS Violation Alerts (Tickets)
    # ====================
    if message.channel.category_id in TICKET_CATEGORY_IDS:
        content_lower = message.content.lower()

        # Check for DM exchange attempts (CRITICAL)
        if any(word in content_lower for word in ["dm me", "message me", "pm me"]):
            try:
                embed = discord.Embed(
                    title="🚨 CRITICAL TOS VIOLATION",
                    description=(
                        "**EXCHANGES MUST ONLY HAPPEN IN TICKETS - NEVER IN DMS!**\n\n"
                        "Anyone asking to exchange via DM is trying to scam you. "
                        "All legitimate exchanges happen here in the ticket with staff oversight.\n\n"
                        "**If someone asks you to DM them, report to staff immediately!**"
                    ),
                    color=discord.Color.red()
                )
                embed.set_footer(text="Afroo Exchange AI - Protecting You")
                await message.channel.send(embed=embed)

                logger.critical(f"CRITICAL: DM exchange attempt in {message.channel.name}")

            except Exception as e:
                logger.error(f"Error posting TOS alert: {e}")

        # Check for other severe violations
        severe_violations = ["refuse to pay", "won't pay", "wont pay", "keeping your money", "not sending"]
        if any(violation in content_lower for violation in severe_violations):
            try:
                async with message.channel.typing():
                    tos_check = await get_ai_response(
                        f"Analyze this for TOS violations: '{message.content[:300]}'",
                        "Explain if this violates TOS and cite rules."
                    )

                    embed = discord.Embed(
                        title="Potential TOS Violation Detected",
                        description=tos_check,
                        color=discord.Color.orange()
                    )
                    embed.set_footer(text="Contact staff if you need help")
                    await message.channel.send(embed=embed)

            except Exception as e:
                logger.error(f"Error checking TOS: {e}")

    # Process commands
    await bot.process_commands(message)


async def should_respond_to_message(message: discord.Message) -> tuple[bool, str]:
    """Determine if AI should respond"""

    content_lower = message.content.lower()

    # Always respond if mentioned
    if bot.user in message.mentions:
        return True, "mentioned"

    # General Chat - only moderation
    if message.channel.id == GENERAL_CHAT_ID:
        return False, "general"

    # Exchanger Chat - ONLY respond to clear questions
    if message.channel.id == EXCHANGER_CHAT_ID:
        # Must have a question mark to be considered a question
        if "?" not in message.content:
            return False, "exchanger_general"

        # Only respond to specific question types
        question_keywords = [
            "how do i", "how to", "what is", "what are", "where", "when",
            "can i", "should i", "do i have to", "do i need",
            "claim", "deposit", "fee", "ticket", "payout"
        ]

        if any(keyword in content_lower for keyword in question_keywords):
            return True, "exchanger_question"

        return False, "exchanger_general"

    # Ticket Channels - LESS AGGRESSIVE (only when mentioned or serious issues)
    if message.channel.category_id in TICKET_CATEGORY_IDS:
        # Only respond if someone directly asks the AI or mentions TOS
        if any(word in content_lower for word in ["@afroo ai", "@ai", "afroo ai", "ai help"]):
            return True, "ticket_help"

        # Don't auto-respond to general conversation in tickets
        # Let TOS violation handler below catch critical issues
        return False, "ticket_general"

    return False, "none"


# ====================
# Background Tasks
# ====================

@tasks.loop(minutes=30)
async def purge_general_chat():
    """Purge General Chat every 30 minutes"""
    global NEXT_PURGE_TIME

    if not GENERAL_CHAT_ID:
        return

    try:
        channel = bot.get_channel(GENERAL_CHAT_ID)
        if not channel:
            return

        deleted = await channel.purge(limit=1000, check=lambda m: not m.pinned)

        NEXT_PURGE_TIME = datetime.now() + timedelta(minutes=30)

        embed = discord.Embed(
            title="🧹 Channel Purged",
            description=f"Deleted **{len(deleted)}** message(s).\nNext purge: <t:{int(NEXT_PURGE_TIME.timestamp())}:R>",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Afroo Exchange AI")

        await channel.send(embed=embed)
        logger.info(f"Purged {len(deleted)} messages from General Chat")

    except Exception as e:
        logger.error(f"Error purging: {e}")


@purge_general_chat.before_loop
async def before_purge():
    await bot.wait_until_ready()


# ====================
# Commands
# ====================

@bot.command(name="status", help="Check AI status")
async def status_command(ctx):
    """Check status"""
    embed = discord.Embed(
        title="🤖 Afroo Exchange AI Status",
        color=discord.Color.green()
    )

    embed.add_field(name="AI System", value="Afroo Custom AI ", inline=True)
    embed.add_field(name="TOS Loaded", value="" if TOS_CONTEXT else "", inline=True)
    embed.add_field(
        name="Monitoring",
        value=f"General: {'' if GENERAL_CHAT_ID else ''}\n"
              f"Exchanger: {'' if EXCHANGER_CHAT_ID else ''}\n"
              f"Tickets: {'' if TICKET_CATEGORY_IDS else ''}",
        inline=False
    )

    if NEXT_PURGE_TIME:
        embed.add_field(name="Next Purge", value=f"<t:{int(NEXT_PURGE_TIME.timestamp())}:R>", inline=False)

    embed.set_footer(text="Afroo Exchange AI")
    await ctx.send(embed=embed)


@bot.command(name="tos", help="Get TOS information")
async def tos_command(ctx, *, query: str = None):
    """Get TOS info"""
    await ensure_tos_loaded()

    if not query:
        embed = discord.Embed(
            title="📜 Afroo Exchange TOS",
            description=f"View full TOS: {TOS_URL}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Critical Rule",
            value="**EXCHANGES ONLY IN TICKETS - NEVER IN DMS!**",
            inline=False
        )
        embed.set_footer(text="Afroo Exchange AI")
        await ctx.send(embed=embed)
        return

    async with ctx.typing():
        try:
            response = await get_ai_response(
                f"Question about TOS: {query}",
                "Answer based on TOS context."
            )
            await ctx.reply(response)
        except:
            await ctx.reply("Error retrieving TOS information.")


# ====================
# Main
# ====================

if __name__ == "__main__":
    if not TOKEN:
        logger.error("AI_BOT_TOKEN not found")
        exit(1)

    if not ai_client:
        logger.error("No AI provider configured")
        exit(1)

    logger.info("🤖 Starting Afroo Exchange AI...")

    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("👋 Afroo Exchange AI shutdown")
    except Exception as e:
        logger.error(f"Afroo Exchange AI crashed: {e}", exc_info=True)
