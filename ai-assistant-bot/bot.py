"""
Afroo AI Assistant Bot
Smart helper for FAQ, formatting, and user assistance
"""

import discord
from discord.ext import commands
import os
import logging
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv("AI_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# System prompt for AI assistant
SYSTEM_PROMPT = """You are the Afroo Exchange AI Assistant, a helpful bot for the Afroo cryptocurrency exchange platform.

Your role:
- Answer questions about Afroo Exchange features
- Help users understand how to use the platform
- Provide guidance on cryptocurrency exchanges, wallets, and support
- Format and structure information clearly
- Suggest best practices for crypto trading

Important guidelines:
- Be friendly, helpful, and concise
- Never give financial advice or investment recommendations
- Always remind users to verify information with official support for critical matters
- Don't make decisions for users - help them make informed choices
- Keep responses under 2000 characters (Discord limit)

Available Afroo features:
- Multi-currency wallets (BTC, ETH, USDT, etc.)
- Peer-to-peer exchange creation and matching
- Support ticket system
- Partner program with API access
- KYC verification system
"""


@bot.event
async def on_ready():
    """Bot startup event"""
    logger.info(f"AI Assistant connected as {bot.user}")
    logger.info(f"Connected to {len(bot.guilds)} guilds")

    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="questions | !ask <question>"
        )
    )


@bot.event
async def on_message(message):
    """Handle messages"""
    # Ignore bot messages
    if message.author.bot:
        return

    # Process commands
    await bot.process_commands(message)


@bot.command(name="ask", help="Ask the AI assistant a question")
async def ask(ctx, *, question: str):
    """Ask AI assistant a question"""
    async with ctx.typing():
        try:
            response = await get_ai_response(question, ctx.author.name)

            # Split long responses
            if len(response) > 2000:
                chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                for chunk in chunks:
                    await ctx.reply(chunk)
            else:
                await ctx.reply(response)

        except Exception as e:
            logger.error(f"AI response error: {e}")
            await ctx.reply("Sorry, I encountered an error processing your question. Please try again.")


@bot.command(name="faq", help="Show frequently asked questions")
async def faq(ctx):
    """Show FAQ"""
    embed = discord.Embed(
        title="📚 Frequently Asked Questions",
        description="Common questions about Afroo Exchange",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="How do I create a wallet?",
        value="Use `/wallet-create` command in the main bot to generate a new wallet.",
        inline=False
    )

    embed.add_field(
        name="How do I create an exchange?",
        value="Use `/exchange-create` with your offer details. Others can accept your exchange.",
        inline=False
    )

    embed.add_field(
        name="How do I get support?",
        value="Use `/ticket-create` to open a support ticket. Our team will respond shortly.",
        inline=False
    )

    embed.add_field(
        name="Is there a fee?",
        value="Afroo charges a 1% platform fee on exchanges. No fees for wallet creation.",
        inline=False
    )

    embed.add_field(
        name="How long do exchanges take?",
        value="Exchange offers expire after 24 hours if not accepted. Completed exchanges depend on blockchain confirmation times.",
        inline=False
    )

    embed.set_footer(text="Use !ask <question> for more specific questions")
    await ctx.send(embed=embed)


@bot.command(name="guide", help="Show user guides")
async def guide(ctx, topic: str = None):
    """Show guides"""
    if not topic:
        embed = discord.Embed(
            title="📖 User Guides",
            description="Available guides:",
            color=discord.Color.green()
        )
        embed.add_field(
            name="!guide wallets",
            value="Learn about wallet management",
            inline=False
        )
        embed.add_field(
            name="!guide exchanges",
            value="Learn how to create and manage exchanges",
            inline=False
        )
        embed.add_field(
            name="!guide security",
            value="Security best practices",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    if topic.lower() == "wallets":
        embed = discord.Embed(
            title="Wallet Guide",
            description="How to manage your cryptocurrency wallets",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Creating a Wallet",
            value="Use `/wallet-create` to generate a new wallet. Choose your blockchain and network.",
            inline=False
        )
        embed.add_field(
            name="Checking Balance",
            value="Use `/wallet-balance <wallet_id>` to check your balance.",
            inline=False
        )
        embed.add_field(
            name="Sending Crypto",
            value="Use `/wallet-send` with wallet ID, recipient address, and amount.",
            inline=False
        )
        embed.add_field(
            name="Security",
            value="Never share your private keys! Afroo encrypts them securely.",
            inline=False
        )
        await ctx.send(embed=embed)

    elif topic.lower() == "exchanges":
        embed = discord.Embed(
            title="Exchange Guide",
            description="How to create and manage exchanges",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Creating an Exchange",
            value="Use `/exchange-create` with currencies and amounts. Set your desired exchange rate.",
            inline=False
        )
        embed.add_field(
            name="Finding Exchanges",
            value="Use `/exchange-list` to see available exchanges from other users.",
            inline=False
        )
        embed.add_field(
            name="Accepting an Exchange",
            value="Use `/exchange-accept <exchange_id>` to accept someone's offer.",
            inline=False
        )
        embed.add_field(
            name="Canceling",
            value="Use `/exchange-cancel <exchange_id>` to cancel your pending exchange.",
            inline=False
        )
        await ctx.send(embed=embed)

    elif topic.lower() == "security":
        embed = discord.Embed(
            title="🔒 Security Best Practices",
            description="Keep your account and funds safe",
            color=discord.Color.red()
        )
        embed.add_field(
            name="1. Never Share Private Keys",
            value="Your private keys are encrypted and stored securely. Never share them with anyone.",
            inline=False
        )
        embed.add_field(
            name="2. Verify Addresses",
            value="Always double-check recipient addresses before sending crypto.",
            inline=False
        )
        embed.add_field(
            name="3. Start Small",
            value="Test with small amounts before making large transactions.",
            inline=False
        )
        embed.add_field(
            name="4. Use Official Channels",
            value="Only use official Afroo bot commands. Beware of scammers impersonating staff.",
            inline=False
        )
        embed.add_field(
            name="5. Report Suspicious Activity",
            value="Create a support ticket immediately if you notice anything suspicious.",
            inline=False
        )
        await ctx.send(embed=embed)

    else:
        await ctx.send("❓ Unknown guide topic. Use `!guide` to see available topics.")


@bot.command(name="calculate", help="Calculate exchange rates")
async def calculate(ctx, amount: float, from_currency: str, to_currency: str, rate: float):
    """Calculate exchange amounts"""
    try:
        result = amount * rate
        platform_fee = amount * 0.01  # 1% fee
        net_amount = amount - platform_fee

        embed = discord.Embed(
            title="🧮 Exchange Calculator",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Sending",
            value=f"{amount} {from_currency.upper()}",
            inline=True
        )
        embed.add_field(
            name="Rate",
            value=f"{rate}",
            inline=True
        )
        embed.add_field(
            name="Receiving",
            value=f"{result:.8f} {to_currency.upper()}",
            inline=True
        )
        embed.add_field(
            name="Platform Fee (1%)",
            value=f"{platform_fee:.8f} {from_currency.upper()}",
            inline=True
        )
        embed.add_field(
            name="Net Sent",
            value=f"{net_amount:.8f} {from_currency.upper()}",
            inline=True
        )
        embed.set_footer(text="Actual blockchain fees may apply")

        await ctx.send(embed=embed)

    except ValueError:
        await ctx.send("Invalid input. Use: `!calculate <amount> <from> <to> <rate>`")


async def get_ai_response(question: str, username: str) -> str:
    """Get response from OpenAI"""
    try:
        response = await openai.ChatCompletion.acreate(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{username} asks: {question}"}
            ],
            max_tokens=500,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


@bot.command(name="help-ai", help="Show AI assistant commands")
async def help_ai(ctx):
    """Show help"""
    embed = discord.Embed(
        title="🤖 AI Assistant Commands",
        description="I'm here to help with questions and information!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="!ask <question>",
        value="Ask me anything about Afroo Exchange",
        inline=False
    )
    embed.add_field(
        name="!faq",
        value="View frequently asked questions",
        inline=False
    )
    embed.add_field(
        name="!guide [topic]",
        value="View user guides (wallets, exchanges, security)",
        inline=False
    )
    embed.add_field(
        name="!calculate",
        value="Calculate exchange rates and fees",
        inline=False
    )

    embed.set_footer(text="AI Assistant | Powered by OpenAI")
    await ctx.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        logger.error("AI_BOT_TOKEN not found in environment variables")
        exit(1)

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - AI responses will not work")

    logger.info("🤖 Starting Afroo AI Assistant Bot...")

    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("👋 AI Assistant shutdown requested")
    except Exception as e:
        logger.error(f"AI Assistant crashed: {e}", exc_info=True)
