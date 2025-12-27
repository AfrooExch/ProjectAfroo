"""
Exchanger Deposit Panel View - V4 Exchanger System
Manages exchanger liquidity deposits, holds, withdrawals, and claim limits
"""

import discord
import logging
import io
import qrcode
from decimal import Decimal
from typing import Optional

from utils.view_manager import PersistentView
from utils.embeds import create_embed, error_embed, get_color
from utils.formatting import format_crypto
from api.errors import APIError, NotFoundError

logger = logging.getLogger(__name__)


# All 14 supported cryptocurrencies (same as wallet)
SUPPORTED_CURRENCIES = [
    "BTC", "LTC", "ETH", "SOL",
    "USDC-SOL", "USDC-ETH",
    "USDT-SOL", "USDT-ETH",
    "XRP", "BNB", "TRX",
    "MATIC", "AVAX", "DOGE"
]

CURRENCY_NAMES = {
    "BTC": "Bitcoin",
    "LTC": "Litecoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "USDC-SOL": "USD Coin (Solana)",
    "USDC-ETH": "USD Coin (Ethereum)",
    "USDT-SOL": "Tether (Solana)",
    "USDT-ETH": "Tether (Ethereum)",
    "XRP": "Ripple",
    "BNB": "Binance Coin",
    "TRX": "Tron",
    "MATIC": "Polygon",
    "AVAX": "Avalanche",
    "DOGE": "Dogecoin"
}

# Same emojis as wallet panel
CURRENCY_EMOJIS = {
    "BTC": "🔶",
    "LTC": "⚪",
    "ETH": "🔷",
    "SOL": "🟣",
    "USDC-SOL": "🔵",
    "USDC-ETH": "🔵",
    "USDT-SOL": "🟢",
    "USDT-ETH": "🟢",
    "XRP": "💙",
    "BNB": "💛",
    "TRX": "🔴",
    "MATIC": "🟣",
    "AVAX": "🔴",
    "DOGE": "🐶"
}

CURRENCY_EMOJI_NAMES = {
    "BTC": "BTC",
    "LTC": "LTC",
    "ETH": "ETH",
    "SOL": "SOL",
    "USDC-SOL": "USDC",
    "USDC-ETH": "USDC",
    "USDT-SOL": "USDT",
    "USDT-ETH": "USDT",
    "XRP": "XRP",
    "BNB": "BINANCE",
    "TRX": "TRX",
    "MATIC": "MATIC",
    "AVAX": "AVAX",
    "DOGE": "DOGE"
}

def get_crypto_emoji(bot, currency: str) -> str:
    """Get server emoji for cryptocurrency in embeds, or fallback to unicode"""
    from config import config
    emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
    if emoji_name and bot:
        try:
            emoji = config.get_emoji(bot, emoji_name)
            if emoji and emoji != "❓":
                return emoji  # Return custom server emoji
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
    # Fallback to unicode if custom emoji not found
    return CURRENCY_EMOJIS.get(currency, "💰")


class CopyAddressView(discord.ui.View):
    """View with copy button for wallet address (mobile-friendly)"""

    def __init__(self, address: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.address = address

    @discord.ui.button(label="📋 Copy Address", style=discord.ButtonStyle.primary)
    async def copy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Button to copy wallet address - sends just text for mobile"""
        await interaction.response.send_message(
            self.address,
            ephemeral=True
        )


class ExchangerDepositPanelView(PersistentView):
    """V4 Exchanger Deposit panel with dropdown menu"""

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)
        self.add_item(ExchangerActionsDropdown(bot))


class ExchangerActionsDropdown(discord.ui.Select):
    """Dropdown for exchanger deposit actions"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot

        options = [
            discord.SelectOption(
                label="Deposit",
                value="deposit",
                description="Create deposit wallet for any crypto to raise claim limit"
            ),
            discord.SelectOption(
                label="My Balance & Holds",
                value="balances",
                description="View balances, held funds, and available amounts"
            ),
            discord.SelectOption(
                label="Withdraw",
                value="withdraw",
                description="Withdraw free funds (not held or fee-reserved)"
            ),
            discord.SelectOption(
                label="History",
                value="history",
                description="View deposit and withdrawal transaction history"
            ),
            discord.SelectOption(
                label="Refresh",
                value="refresh",
                description="Sync all deposit balances with blockchain"
            ),
            discord.SelectOption(
                label="Ask Question",
                value="ask_question",
                description="Send anonymous question to unclaimed ticket"
            ),
            discord.SelectOption(
                label="Role Preference",
                value="role_preference",
                description="Choose which tickets you want to be pinged for"
            ),
        ]

        super().__init__(
            placeholder="Choose an action...",
            options=options,
            custom_id="exchanger_deposit_actions_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        action = self.values[0]

        try:
            if action == "deposit":
                await self.show_deposit_options(interaction)
            elif action == "balances":
                await self.show_balances(interaction)
            elif action == "withdraw":
                await self.show_withdraw_options(interaction)
            elif action == "history":
                await self.show_history_options(interaction)
            elif action == "refresh":
                await self.refresh_all_balances(interaction)
            elif action == "ask_question":
                await self.show_ask_question(interaction)
            elif action == "role_preference":
                await self.show_role_preference(interaction)

        except Exception as e:
            logger.error(f"Error in exchanger dropdown: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=error_embed(
                    description=(
                        "❌ Something went wrong while processing your request.\n\n"
                        "**What to do:**\n"
                        "> • Try selecting the action again\n"
                        "> • If the problem persists, contact support"
                    )
                ),
                ephemeral=True
            )

    async def show_deposit_options(self, interaction: discord.Interaction):
        """Show crypto selection for deposit (creates separate exchanger wallet)"""
        view = ExchangerCryptoSelectorView(self.bot, mode="deposit")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    "## 💼 Select Cryptocurrency\n\n"
                    "Choose which crypto you want to deposit.\n\n"
                    "> A **separate exchanger deposit wallet** will be created\n"
                    "> This is different from your regular wallet\n"
                    "> Deposits increase your claim limit (1:1 ratio)"
                ),
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def show_balances(self, interaction: discord.Interaction):
        """Show exchanger deposit balances with held amounts"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get all exchanger deposits
            result = await api.exchanger_list_deposits(user_id)
            deposits = result.get("deposits", [])

            # Get claim limit info
            claim_info = await api.exchanger_get_claim_limit(user_id)
            claim_limit_data = claim_info.get("claim_limit", {})

            if not deposits:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💼 Exchanger Deposits\n\n"
                            "> You don't have any exchanger deposits yet.\n"
                            "> Use the **Deposit** option to create a deposit wallet!\n\n"
                            "**How it works:**\n"
                            "> • Deposit crypto to raise your claim limit\n"
                            "> • $100 deposited = $100 claim limit (1:1 ratio)\n"
                            "> • Funds are held when you claim tickets\n"
                            "> • Withdraw free funds anytime"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Build description with claim limit at top
            description = "## 💼 Exchanger Deposits\n\n"
            description += "**Claim Limit:**\n```\n"
            description += f"Total Deposits: ${claim_limit_data.get('total_deposit_usd', '0')} USD\n"
            description += f"Total Held:     ${claim_limit_data.get('total_held_usd', '0')} USD\n"
            description += f"Fee Reserved:   ${claim_limit_data.get('total_fee_reserved_usd', '0')} USD\n"
            description += f"Claim Limit:    ${claim_limit_data.get('claim_limit_usd', '0')} USD\n"
            description += f"Available:      ${claim_limit_data.get('available_to_claim_usd', '0')} USD\n"
            description += "```\n\n"

            # Show each deposit with USD values
            for deposit in deposits:
                currency = deposit["currency"]
                emoji = get_crypto_emoji(self.bot, currency)
                name = CURRENCY_NAMES.get(currency, currency)
                wallet_address = deposit.get("wallet_address", "")

                balance = deposit.get("balance", "0")
                held = deposit.get("held", "0")
                fee_reserved = deposit.get("fee_reserved", "0")
                available = deposit.get("available", "0")
                is_active = deposit.get("is_active", True)

                # Get detailed balance with USD values
                try:
                    balance_result = await api.exchanger_get_deposit(user_id, currency)
                    balance_data = balance_result.get("balance", {})
                    balance_usd = balance_data.get("balance_usd", "0")
                    held_usd = balance_data.get("held_usd", "0")
                    fee_reserved_usd = balance_data.get("fee_reserved_usd", "0")
                    available_usd = balance_data.get("available_usd", "0")
                except Exception as e:
                    balance_usd = held_usd = fee_reserved_usd = available_usd = "0"

                status_indicator = "✅" if is_active else "❌"

                description += f"{emoji} **{name}** ({currency}) {status_indicator}\n"
                description += f"> Address: `{wallet_address}`\n"
                description += f"```\n"
                description += f"Balance:      {balance} {currency} (${float(balance_usd):.2f})\n"

                if held != "0" or float(held_usd) > 0:
                    description += f"Held:         {held} {currency} (${float(held_usd):.2f})\n"
                if fee_reserved != "0" or float(fee_reserved_usd) > 0:
                    description += f"Fee Reserved: {fee_reserved} {currency} (${float(fee_reserved_usd):.2f})\n"

                description += f"Available:    {available} {currency} (${float(available_usd):.2f})\n"
                description += f"```\n"

            description += "\n> **Held** = Locked in active tickets\n"
            description += "> **Fee Reserved** = Reserved for platform fees (2%)\n"
            description += "> **Available** = Free to withdraw"

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"Exchanger balances API error: {e}")
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Exchanger balances error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load your exchanger deposits right now.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if the bot is online\n"
                        "> • Contact support if this keeps happening"
                    )
                ),
                ephemeral=True
            )

    async def show_withdraw_options(self, interaction: discord.Interaction):
        """Show crypto selection for withdrawal (only free funds)"""
        view = ExchangerCryptoSelectorView(self.bot, mode="withdraw")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    "## 💼 Select Cryptocurrency\n\n"
                    "Choose which crypto you want to withdraw.\n\n"
                    "> ⚠️ You can only withdraw **free funds**\n"
                    "> Held and fee-reserved funds cannot be withdrawn\n"
                    "> Network fee will be deducted from withdrawal"
                ),
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def show_history_options(self, interaction: discord.Interaction):
        """Show crypto selection for transaction history"""
        view = ExchangerCryptoSelectorView(self.bot, mode="history")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    "## 💼 Select Cryptocurrency\n\n"
                    "Choose which crypto's history you want to view:"
                ),
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def refresh_all_balances(self, interaction: discord.Interaction):
        """Refresh all exchanger deposit balances with latest on-chain data"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get current deposits
            result = await api.exchanger_list_deposits(user_id)
            deposits_before = result.get("deposits", [])

            if not deposits_before:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💼 Exchanger Deposits\n\n"
                            "> You don't have any exchanger deposits yet\n"
                            "> Use the **Deposit** option to create a deposit wallet"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Show progress message
            total_deposits = len(deposits_before)
            await interaction.followup.send(
                embed=create_embed(
                    title="",
                    description=f"## 💼 Exchanger Deposits\n\n> Syncing {total_deposits} deposit wallet(s) with blockchain...",
                    color=get_color("primary")
                ),
                ephemeral=True
            )

            # Sync all deposits with blockchain
            synced_count = 0
            failed_currencies = []

            for deposit in deposits_before:
                currency = deposit["currency"]
                try:
                    await api.exchanger_sync_deposit(user_id, currency)
                    synced_count += 1
                except Exception as sync_err:
                    logger.warning(f"Failed to sync exchanger deposit {currency} for {user_id}: {sync_err}")
                    failed_currencies.append(currency)

            # Get updated deposits
            result_after = await api.exchanger_list_deposits(user_id)
            deposits_after = result_after.get("deposits", [])

            # Check for balance changes
            balance_changes = []
            deposits_before_dict = {d["currency"]: d.get("balance", "0") for d in deposits_before}
            for deposit in deposits_after:
                currency = deposit["currency"]
                new_balance = deposit.get("balance", "0")
                old_balance = deposits_before_dict.get(currency, "0")

                if new_balance != old_balance:
                    balance_changes.append({
                        "currency": currency,
                        "old": old_balance,
                        "new": new_balance
                    })

            # Build result message
            description = "## 💼 Exchanger Deposits\n\n"
            description += f"**Synced:** {synced_count}/{total_deposits} deposit wallet(s)\n\n"

            if balance_changes:
                description += "**Balance Changes:**\n"
                for change in balance_changes:
                    currency = change["currency"]
                    emoji = get_crypto_emoji(self.bot, currency)
                    name = CURRENCY_NAMES.get(currency, currency)

                    try:
                        old_float = float(change["old"]) if change["old"] != "0" else 0
                        new_float = float(change["new"]) if change["new"] != "0" else 0
                        diff = new_float - old_float
                        diff_str = f"+{diff:.8f}" if diff > 0 else f"{diff:.8f}"
                    except Exception as e:
                        diff_str = "?"

                    description += f"{emoji} **{name}**: `{diff_str}` {currency}\n"
            else:
                description += "> No balance changes detected"

            if failed_currencies:
                description += f"\n\n> Failed to sync: {', '.join(failed_currencies)}"

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            # Send final results as new message
            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"Refresh exchanger deposits API error: {e}")
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Refresh exchanger deposits error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to refresh exchanger deposits right now.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if the bot is online\n"
                        "> • Contact support if this keeps happening"
                    )
                ),
                ephemeral=True
            )

    async def show_ask_question(self, interaction: discord.Interaction):
        """Show Ask Question flow - select ticket then select question"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get awaiting_claim tickets
            result = await api.exchanger_get_awaiting_tickets(user_id, limit=25)
            tickets = result.get("tickets", [])

            if not tickets:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💼 Ask Question\n\n"
                            "> No unclaimed tickets available right now\n"
                            "> Check back later when tickets are awaiting claim"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Show ticket selector
            view = AskQuestionTicketSelector(self.bot, tickets)

            await interaction.followup.send(
                embed=create_embed(
                    title="",
                    description=(
                        f"## 💼 Ask Question\n\n"
                        f"Select a ticket to ask an anonymous question:\n\n"
                        f"> Found **{len(tickets)}** unclaimed ticket(s)\n"
                        f"> Your question will be posted anonymously\n"
                        f"> Customer won't see your identity"
                    ),
                    color=get_color("primary")
                ),
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Ask question error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load tickets right now.\n\n"
                        "**What to do:**\n"
                        "> • Try again in a moment\n"
                        "> • Contact support if this persists"
                    )
                ),
                ephemeral=True
            )

    async def show_role_preference(self, interaction: discord.Interaction):
        """Show Role Preference selector"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get current preferences
            result = await api.exchanger_get_preferences(user_id)
            prefs = result.get("preferences", {})

            # Show preference selector
            view = RolePreferenceView(self.bot, prefs)

            current_methods = prefs.get("preferred_payment_methods", [])
            notifications = prefs.get("notifications_enabled", True)

            description = "## 💼 Role Preference\n\n"
            description += "Choose which tickets you want to be pinged for:\n\n"

            if current_methods:
                description += "**Current Preferences:**\n"
                for method in current_methods:
                    description += f"> • {method.replace('_', ' ').title()}\n"
            else:
                description += "> Currently: **All tickets** (no filter)\n"

            description += f"\n**Notifications:** {'✅ Enabled' if notifications else '❌ Disabled'}"

            await interaction.followup.send(
                embed=create_embed(
                    title="",
                    description=description,
                    color=get_color("primary")
                ),
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Role preference error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load preferences right now.\n\n"
                        "**What to do:**\n"
                        "> • Try again in a moment\n"
                        "> • Contact support if this persists"
                    )
                ),
                ephemeral=True
            )


class AskQuestionTicketSelector(discord.ui.View):
    """View for selecting ticket to ask question on"""

    def __init__(self, bot: discord.Bot, tickets: list):
        super().__init__()
        self.bot = bot

        # Create dropdown with tickets (max 25)
        options = []
        for i, ticket in enumerate(tickets[:25]):
            ticket_id = ticket.get("ticket_id", "Unknown")
            amount = ticket.get("amount_usd", 0)
            send_method = ticket.get("send_method", "Unknown")
            receive_method = ticket.get("receive_method", "Unknown")

            options.append(discord.SelectOption(
                label=f"Ticket #{ticket_id} - ${amount} USD",
                value=ticket_id,
                description=f"{send_method} → {receive_method}"
            ))

        select = discord.ui.Select(
            placeholder="Select a ticket...",
            options=options
        )
        select.callback = lambda i: self.ticket_selected(i, select)
        self.add_item(select)

    async def ticket_selected(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle ticket selection"""
        ticket_id = select.values[0]
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client

            # Get preset questions
            result = await api.exchanger_get_preset_questions()
            questions = result.get("questions", [])

            # Show question selector
            view = AskQuestionSelector(self.bot, ticket_id, questions)

            await interaction.followup.send(
                embed=create_embed(
                    title="",
                    description=(
                        f"## 💼 Ask Question\n\n"
                        f"**Ticket:** #{ticket_id}\n\n"
                        f"Select a question to ask:"
                    ),
                    color=get_color("primary")
                ),
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Ticket selection error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(description="❌ Unable to load questions"),
                ephemeral=True
            )


class AskQuestionSelector(discord.ui.View):
    """View for selecting which question to ask"""

    def __init__(self, bot: discord.Bot, ticket_id: str, questions: list):
        super().__init__()
        self.bot = bot
        self.ticket_id = ticket_id
        self.questions = questions

        # Split into two dropdowns if more than 12 questions
        chunk_1 = questions[:12]
        chunk_2 = questions[12:] if len(questions) > 12 else []

        # First dropdown
        options_1 = []
        for q in chunk_1:
            q_id = q.get("id")
            q_text = q.get("text")
            q_type = q.get("type")

            options_1.append(discord.SelectOption(
                label=q_text[:100] if len(q_text) > 100 else q_text,
                value=q_id,
                description=f"Type: {q_type}"
            ))

        select_1 = discord.ui.Select(
            placeholder="Choose a question...",
            options=options_1
        )
        select_1.callback = lambda i: self.question_selected(i, select_1)
        self.add_item(select_1)

        # Second dropdown if needed
        if chunk_2:
            options_2 = []
            for q in chunk_2:
                q_id = q.get("id")
                q_text = q.get("text")
                q_type = q.get("type")

                options_2.append(discord.SelectOption(
                    label=q_text[:100] if len(q_text) > 100 else q_text,
                    value=q_id,
                    description=f"Type: {q_type}"
                ))

            select_2 = discord.ui.Select(
                placeholder="More questions...",
                options=options_2
            )
            select_2.callback = lambda i: self.question_selected(i, select_2)
            self.add_item(select_2)

    async def question_selected(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle question selection"""
        question_id = select.values[0]

        # Find the question
        question = None
        for q in self.questions:
            if q.get("id") == question_id:
                question = q
                break

        if not question:
            await interaction.response.send_message(
                embed=error_embed(description="❌ Question not found"),
                ephemeral=True
            )
            return

        question_type = question.get("type")

        # Handle special question types
        if question_type == "alt_payment":
            # Show payment method selector
            await self.show_alt_payment_selector(interaction, question)
        elif question_type == "alt_amount":
            # Show amount input modal
            modal = AltAmountModal(self.bot, self.ticket_id, question)
            await interaction.response.send_modal(modal)
        else:
            # Regular question - send immediately
            await self.send_question(interaction, question)

    async def show_alt_payment_selector(self, interaction: discord.Interaction, question: dict):
        """Show payment method selector for alt_payment question"""
        from utils.payment_methods import PAYMENT_METHODS

        view = discord.ui.View()

        # Create dropdown with payment methods
        options = []
        for key, method in list(PAYMENT_METHODS.items())[:25]:  # Max 25
            options.append(discord.SelectOption(
                label=method.display_name,
                value=method.value,
                emoji=method.emoji_fallback
            ))

        select = discord.ui.Select(
            placeholder="Select alternative payment method...",
            options=options
        )

        async def payment_selected(i: discord.Interaction):
            alt_payment = select.values[0]
            await self.send_question(i, question, alt_payment_method=alt_payment)

        select.callback = payment_selected
        view.add_item(select)

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    "## 💼 Ask Question\n\n"
                    "Select alternative payment method to offer:"
                ),
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def send_question(
        self,
        interaction: discord.Interaction,
        question: dict,
        alt_payment_method: Optional[str] = None,
        alt_amount_usd: Optional[str] = None
    ):
        """Send the question via API"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            result = await api.exchanger_ask_question(
                user_id=user_id,
                ticket_id=self.ticket_id,
                question_text=question.get("text"),
                question_type=question.get("type", "preset"),
                alt_payment_method=alt_payment_method,
                alt_amount_usd=alt_amount_usd
            )

            if result.get("success"):
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💼 Question Sent!\n\n"
                            f"> Your anonymous question has been posted to ticket #{self.ticket_id}\n"
                            f"> The customer will see your question but not your identity"
                        ),
                        color=get_color("success")
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=error_embed(description="❌ Failed to send question"),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Send question error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(description=f"❌ Error: {str(e)}"),
                ephemeral=True
            )


class AltAmountModal(discord.ui.Modal):
    """Modal for entering alternative amount"""

    def __init__(self, bot: discord.Bot, ticket_id: str, question: dict):
        super().__init__(title="Alternative Amount")
        self.bot = bot
        self.ticket_id = ticket_id
        self.question = question

        self.amount_input = discord.ui.InputText(
            label="Alternative Amount (USD)",
            placeholder="Enter amount in USD (e.g., 50.00)",
            required=True,
            max_length=20
        )

        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle amount submission"""
        await interaction.response.defer(ephemeral=True)

        alt_amount = self.amount_input.value.strip()

        # Validate amount
        try:
            amount_float = float(alt_amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            await interaction.followup.send(
                embed=error_embed(description="❌ Invalid amount. Please enter a valid number."),
                ephemeral=True
            )
            return

        # Send question with alt_amount
        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            result = await api.exchanger_ask_question(
                user_id=user_id,
                ticket_id=self.ticket_id,
                question_text=self.question.get("text"),
                question_type="alt_amount",
                alt_amount_usd=alt_amount
            )

            if result.get("success"):
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💼 Question Sent!\n\n"
                            f"> Your anonymous question has been posted to ticket #{self.ticket_id}\n"
                            f"> Alternative amount: ${alt_amount} USD\n"
                            f"> The customer will see your question but not your identity"
                        ),
                        color=get_color("success")
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=error_embed(description="❌ Failed to send question"),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Send alt_amount question error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(description=f"❌ Error: {str(e)}"),
                ephemeral=True
            )


class RolePreferenceView(discord.ui.View):
    """View for managing role preferences"""

    def __init__(self, bot: discord.Bot, current_prefs: dict):
        super().__init__()
        self.bot = bot
        self.current_prefs = current_prefs

        # Add payment method selector - ONLY 11 main payment methods
        # Each method shows only once (no separate balance/card options)
        allowed_methods = [
            "paypal_balance",      # PayPal
            "cashapp_balance",     # CashApp
            "applepay_balance",    # ApplePay
            "venmo_balance",       # Venmo
            "zelle",               # Zelle
            "chime",               # Chime
            "revolut",             # Revolut
            "skrill_balance",      # Skrill
            "bank_transfer",       # Bank
            "paysafe",             # PaySafe
            "binance_gift_card"    # Binance
        ]

        from utils.payment_methods import PAYMENT_METHODS
        from config import config

        # Get guild to fetch custom emojis
        guild = bot.get_guild(config.guild_id) if bot else None

        options = []
        current_methods = current_prefs.get("preferred_payment_methods", [])

        for key, method in PAYMENT_METHODS.items():
            # Only include methods with roles
            if method.value not in allowed_methods:
                continue

            # Check if currently selected
            default = method.value in current_methods

            # Try to get custom server emoji first, fallback to unicode
            emoji = None
            if guild and method.emoji_name:
                emoji = discord.utils.get(guild.emojis, name=method.emoji_name)

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = method.emoji_fallback

            options.append(discord.SelectOption(
                label=method.display_name,
                value=method.value,
                emoji=emoji,
                default=default
            ))

        select = discord.ui.Select(
            placeholder="Select payment methods...",
            options=options,
            min_values=0,  # Allow unselecting all
            max_values=len(options)  # Allow selecting multiple
        )
        select.callback = self.preferences_updated
        self.add_item(select)

    async def preferences_updated(self, interaction: discord.Interaction):
        """Handle preference update"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get selected methods
            selected_methods = interaction.data.get("values", [])

            # Update preferences
            result = await api.exchanger_update_preferences(
                user_id=user_id,
                preferred_payment_methods=selected_methods
            )

            if result.get("success"):
                # Assign/remove Discord roles based on payment method selection
                # Map payment method values to role IDs
                method_role_map = {
                    "paypal_balance": 1431732911140503583,    # PayPal Exchanger
                    "cashapp_balance": 1431733031999377428,   # CashApp Exchanger
                    "applepay_balance": 1431733169777938594,  # ApplePay Exchanger
                    "venmo_balance": 1431733262367326370,     # Venmo Exchanger
                    "zelle": 1431733429929775104,             # Zelle Exchanger
                    "chime": 1431733785086394408,             # Chime Exchanger
                    "revolut": 1431734050217005136,           # Revolut Exchanger
                    "skrill_balance": 1431734179086860468,    # Skrill Exchanger
                    "bank_transfer": 1431734579290570752,     # Bank Exchanger
                    "paysafe": 1431734710744387684,           # PaySafe Exchanger
                    "binance_gift_card": 1431734831028633650, # Binance Gift Card Exchanger
                }

                # Get guild and member object
                guild = interaction.guild
                # Fetch full Member object from guild (interaction.user may be limited)
                member = guild.get_member(interaction.user.id)

                if not member:
                    await interaction.followup.send(
                        embed=error_embed(description="❌ Unable to update your Discord roles. Please try again."),
                        ephemeral=True
                    )
                    return

                # Get all exchanger payment method roles
                all_payment_roles = set(method_role_map.values())
                all_payment_roles.discard(0)  # Remove 0 (unconfigured roles)

                # Determine which roles to add/remove
                selected_role_ids = set()
                for method in selected_methods:
                    role_id = method_role_map.get(method, 0)
                    if role_id and role_id > 0:
                        selected_role_ids.add(role_id)

                # Get member's current roles
                current_role_ids = {role.id for role in member.roles}

                # Roles to add (selected but not currently assigned)
                roles_to_add = selected_role_ids - current_role_ids

                # Roles to remove (payment method roles they have but didn't select)
                roles_to_remove = (all_payment_roles & current_role_ids) - selected_role_ids

                # Assign new roles
                for role_id in roles_to_add:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            await member.add_roles(role, reason="Exchanger payment method preference selected")
                            logger.info(f"Assigned role {role.name} to {member.id}")
                        except Exception as e:
                            logger.error(f"Failed to assign role {role_id}: {e}")

                # Remove deselected roles
                for role_id in roles_to_remove:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            await member.remove_roles(role, reason="Exchanger payment method preference deselected")
                            logger.info(f"Removed role {role.name} from {member.id}")
                        except Exception as e:
                            logger.error(f"Failed to remove role {role_id}: {e}")

                # Build success message
                if selected_methods:
                    methods_str = "\n".join([f"> • {m.replace('_', ' ').title()}" for m in selected_methods])
                    description = (
                        "## 💼 Preferences Updated!\n\n"
                        "**You will be pinged for:**\n"
                        f"{methods_str}\n\n"
                        "> Other tickets will be filtered out\n"
                        f"> ✅ Discord roles updated"
                    )
                else:
                    description = (
                        "## 💼 Preferences Cleared!\n\n"
                        "> You will be pinged for **all tickets**\n"
                        "> No payment method filter applied\n"
                        f"> ✅ Payment method roles removed"
                    )

                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=description,
                        color=get_color("success")
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=error_embed(description="❌ Failed to update preferences"),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Update preferences error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(description=f"❌ Error: {str(e)}"),
                ephemeral=True
            )


class ExchangerCryptoSelectorView(discord.ui.View):
    """View for selecting cryptocurrency for exchanger operations"""

    def __init__(self, bot: discord.Bot, mode: str):
        super().__init__()
        self.bot = bot
        self.mode = mode  # "deposit", "withdraw", or "history"

        # Split currencies into chunks of 12 each (Discord allows max 25 per select)
        chunk_1 = SUPPORTED_CURRENCIES[:12]
        chunk_2 = SUPPORTED_CURRENCIES[12:]

        # Get guild to fetch custom emojis
        from config import config
        guild = bot.get_guild(config.guild_id) if bot else None

        # First dropdown - use custom server emojis
        options_1 = []
        for currency in chunk_1:
            emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
            emoji = None

            # Try to get custom server emoji
            if guild and emoji_name:
                emoji = discord.utils.get(guild.emojis, name=emoji_name)

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = CURRENCY_EMOJIS.get(currency, "💰")

            options_1.append(discord.SelectOption(
                label=f"{CURRENCY_NAMES.get(currency, currency)} ({currency})",
                value=currency,
                emoji=emoji
            ))

        select_1 = discord.ui.Select(
            placeholder="Popular cryptos...",
            options=options_1
        )
        select_1.callback = lambda i: self.currency_selected(i, select_1)
        self.add_item(select_1)

        # Second dropdown if needed
        if chunk_2:
            options_2 = []
            for currency in chunk_2:
                emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
                emoji = None

                # Try to get custom server emoji
                if guild and emoji_name:
                    emoji = discord.utils.get(guild.emojis, name=emoji_name)

                # Fallback to unicode if custom emoji not found
                if not emoji:
                    emoji = CURRENCY_EMOJIS.get(currency, "💰")

                options_2.append(discord.SelectOption(
                    label=f"{CURRENCY_NAMES.get(currency, currency)} ({currency})",
                    value=currency,
                    emoji=emoji
                ))

            select_2 = discord.ui.Select(
                placeholder="More cryptos...",
                options=options_2
            )
            select_2.callback = lambda i: self.currency_selected(i, select_2)
            self.add_item(select_2)

    async def currency_selected(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle currency selection"""
        currency = select.values[0]
        user_id = str(interaction.user.id)
        api = self.bot.api_client

        try:
            if self.mode == "deposit":
                await interaction.response.defer(ephemeral=True)
                await self.handle_deposit(interaction, api, user_id, currency)
            elif self.mode == "withdraw":
                # Don't defer for withdraw - we need to send modal immediately
                await self.handle_withdraw(interaction, api, user_id, currency)
            elif self.mode == "history":
                await interaction.response.defer(ephemeral=True)
                await self.handle_history(interaction, api, user_id, currency)

        except Exception as e:
            logger.error(f"Exchanger currency selection error: {e}", exc_info=True)
            # Try to send error message - use response if not responded, otherwise followup
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed(
                            description=(
                                "❌ Unable to process your cryptocurrency selection.\n\n"
                                "**What to do:**\n"
                                "> • Try selecting the crypto again\n"
                                "> • Make sure the bot has proper permissions\n"
                                "> • Contact support if the issue continues"
                            )
                        ),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=error_embed(
                            description=(
                                "❌ Unable to process your cryptocurrency selection.\n\n"
                                "**What to do:**\n"
                                "> • Try selecting the crypto again\n"
                                "> • Make sure the bot has proper permissions\n"
                                "> • Contact support if the issue continues"
                            )
                        ),
                        ephemeral=True
                    )
            except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)  # Failed to send error message

    async def handle_deposit(self, interaction, api, user_id, currency):
        """Handle deposit - create or get exchanger deposit wallet"""
        try:
            # Try to get existing deposit
            deposit = await api.exchanger_get_deposit(user_id, currency)
            wallet_address = deposit.get("balance", {}).get("wallet_address")
            balance = deposit.get("balance", {}).get("balance", "0")

        except NotFoundError:
            # Deposit doesn't exist, create it
            try:
                result = await api.exchanger_create_deposit(user_id, currency)
                wallet_address = result.get("wallet_address")
                balance = "0"
            except Exception as gen_error:
                logger.error(f"Failed to create exchanger deposit: {gen_error}")
                await interaction.followup.send(
                    embed=error_embed(
                        description=(
                            f"❌ Unable to create your {currency} exchanger deposit wallet.\n\n"
                            f"**What to do:**\n"
                            f"> • The blockchain service may be temporarily unavailable\n"
                            f"> • Wait a few minutes and try again\n"
                            f"> • Contact support if this error persists"
                        )
                    ),
                    ephemeral=True
                )
                return

        # Generate QR code
        qr_file = self._generate_qr_code(wallet_address)

        name = CURRENCY_NAMES.get(currency, currency)
        emoji = get_crypto_emoji(self.bot, currency)

        embed = create_embed(
            title="",
            description=(
                f"## {emoji} {name} Exchanger Deposit\n\n"
                f"**Deposit Address:**\n"
                f"```\n{wallet_address}\n```\n\n"
                f"**Current Balance:** `{balance} {currency}`\n\n"
                f"> ⚠️ This is your **exchanger deposit wallet**\n"
                f"> Different from your regular wallet\n"
                f"> Deposits increase your claim limit (1:1 ratio)\n"
                f"> Funds may be held when claiming tickets\n"
                f"> Only send {currency} to this address\n"
                f"> Sending other currencies = permanent loss"
            ),
            color=get_color("primary")
        )

        embed.set_image(url="attachment://qr.png")

        # Add copy button for mobile users
        view = CopyAddressView(wallet_address)

        await interaction.followup.send(
            embed=embed,
            file=qr_file,
            view=view,
            ephemeral=True
        )

    async def handle_withdraw(self, interaction, api, user_id, currency):
        """Handle withdraw - show modal (only free funds)"""
        try:
            # DON'T sync before showing modal - it can timeout the interaction
            # Get cached balance first, user can refresh manually if needed

            # Check if deposit exists and get balance
            deposit = await api.exchanger_get_deposit(user_id, currency)

            if not deposit:
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            f"❌ You don't have a {currency} exchanger deposit yet.\n\n"
                            f"**What to do:**\n"
                            f"> • Use **Deposit** to create your {currency} exchanger deposit\n"
                            f"> • Then you can deposit funds and withdraw them"
                        )
                    ),
                    ephemeral=True
                )
                return

            balance_info = deposit.get("balance", {})
            available = balance_info.get("available", "0")
            held = balance_info.get("held", "0")
            fee_reserved = balance_info.get("fee_reserved", "0")

            # Validate available balance
            try:
                available_decimal = Decimal(available)
            except Exception as e:
                logger.error(f"Invalid available balance for {user_id}/{currency}: {available}")
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            "❌ Unable to read deposit balance.\n\n"
                            "**What to do:**\n"
                            "> • Try using **Refresh** first\n"
                            "> • Contact support if this persists"
                        )
                    ),
                    ephemeral=True
                )
                return

            if available_decimal <= 0:
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            f"❌ No free funds available to withdraw.\n\n"
                            f"**Current Status:**\n"
                            f"```\n"
                            f"Balance:      {balance_info.get('balance', '0')} {currency}\n"
                            f"Held:         {held} {currency}\n"
                            f"Fee Reserved: {fee_reserved} {currency}\n"
                            f"Available:    {available} {currency}\n"
                            f"```\n\n"
                            f"**What to do:**\n"
                            f"> • Wait for active tickets to complete\n"
                            f"> • Use **Deposit** to add more {currency}\n"
                            f"> • Check **My Balance & Holds** for details"
                        )
                    ),
                    ephemeral=True
                )
                return

            # Show withdraw modal
            modal = ExchangerWithdrawModal(self.bot, currency, available)
            await interaction.response.send_modal(modal)

        except APIError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                # Only use response if not already used
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed(
                            description=(
                                f"❌ You don't have a {currency} exchanger deposit yet.\n\n"
                                f"**What to do:**\n"
                                f"> • Use **Deposit** to create your {currency} exchanger deposit\n"
                                f"> • Then you can deposit funds and withdraw them"
                            )
                        ),
                        ephemeral=True
                    )
            else:
                logger.error(f"Exchanger withdraw check error: {e}")
                # Only use response if not already used
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed(
                            description=(
                                "❌ Unable to check your exchanger deposit status.\n\n"
                                "**What to do:**\n"
                                "> • The service may be temporarily down\n"
                                "> • Try again in a few moments\n"
                                "> • Contact support if the problem continues"
                            )
                        ),
                        ephemeral=True
                    )

    async def handle_history(self, interaction, api, user_id, currency):
        """Handle transaction history"""
        try:
            # Get transactions from exchanger API
            result = await api.exchanger_get_history(user_id, currency=currency, limit=10)
            transactions = result.get("transactions", [])

            if not transactions:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            f"## 💼 Exchanger Deposits\n\n"
                            f"> No {currency} transactions yet"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Build history description
            name = CURRENCY_NAMES.get(currency, currency)
            emoji = get_crypto_emoji(self.bot, currency)

            description = f"## {emoji} {name} Exchanger History\n\n"

            for tx in transactions[:10]:
                tx_type = tx.get("type", "unknown")
                amount = tx.get("amount", "0")
                status = tx.get("status", "unknown")
                created = tx.get("created_at", "")[:10]  # Date only
                tx_hash = tx.get("tx_hash", "")
                network_fee = tx.get("network_fee", "0")
                to_address = tx.get("to_address")

                # Status indicator
                status_text = {
                    "pending": "⏳ Pending",
                    "confirming": "🔄 Confirming",
                    "confirmed": "✅ Confirmed",
                    "failed": "❌ Failed"
                }.get(status, "❓ Unknown")

                # Build transaction display
                tx_info = f"**{tx_type.title()}** - {status_text}\n```\n"
                tx_info += f"Amount:  {amount} {currency}\n"

                # Show fees for withdrawals
                if tx_type == "withdrawal":
                    if network_fee and network_fee != "0":
                        tx_info += f"Net Fee: {network_fee} {currency}\n"
                    if to_address:
                        tx_info += f"To:      {to_address}\n"

                if tx_hash:
                    tx_info += f"Hash:    {tx_hash}\n"
                tx_info += f"Date:    {created}\n"
                tx_info += f"```\n"

                description += tx_info

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"Exchanger history error: {e}")
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load your transaction history.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if you have any transactions\n"
                        "> • Contact support if this error persists"
                    )
                ),
                ephemeral=True
            )

    def _generate_qr_code(self, data: str) -> discord.File:
        """Generate QR code image"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return discord.File(buffer, filename="qr.png")


class ExchangerWithdrawModal(discord.ui.Modal):
    """Modal for exchanger withdrawal (only free funds)"""

    def __init__(self, bot: discord.Bot, currency: str, max_available: str):
        super().__init__(title=f"Withdraw {currency}")
        self.bot = bot
        self.currency = currency
        self.max_available = max_available

        self.address_input = discord.ui.InputText(
            label="Destination Address",
            placeholder=f"Enter {currency} address...",
            required=True,
            max_length=200
        )

        self.amount_input = discord.ui.InputText(
            label="Amount (or type 'max')",
            placeholder=f"Type 'max' or amount. Available: {max_available} {currency}",
            required=True,
            max_length=50
        )

        self.add_item(self.address_input)
        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle withdrawal submission"""
        await interaction.response.defer(ephemeral=True)

        to_address = self.address_input.value.strip()
        amount = self.amount_input.value.strip()
        user_id = str(interaction.user.id)
        api = self.bot.api_client

        # Validate amount
        if amount.lower() != "max":
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                await interaction.followup.send(
                    embed=error_embed(
                        description=(
                            "❌ Invalid withdrawal amount.\n\n"
                            "**What to do:**\n"
                            f"> • Enter a valid number (e.g., 0.5, 1.25) or 'max'\n"
                            f"> • Amount must be positive\n"
                            f"> • Available balance: {self.max_available} {self.currency}"
                        )
                    ),
                    ephemeral=True
                )
                return

        try:
            # Execute withdrawal (backend enforces free-funds only)
            result = await api.exchanger_withdraw(user_id, self.currency, amount, to_address)

            name = CURRENCY_NAMES.get(self.currency, self.currency)
            emoji = get_crypto_emoji(self.bot, self.currency)

            actual_amount = result.get("amount", amount)
            network_fee = result.get("network_fee", "0")
            tx_hash = result.get("tx_hash", "N/A")

            embed = create_embed(
                title="",
                description=(
                    f"## {emoji} {name} Withdrawal Initiated\n\n"
                    f"**Recipient Gets:** `{actual_amount} {self.currency}`\n"
                    f"**Network Fee:** `{network_fee} {self.currency}`\n\n"
                    f"**To Address:**\n`{to_address}`\n\n"
                    f"**Transaction Hash:**\n`{tx_hash}`\n\n"
                    f"> ✅ Withdrawal broadcast to blockchain\n"
                    f"> ⏳ Balance updates after confirmation\n"
                    f"> 📋 Check **History** for status"
                ),
                color=get_color("success")
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Exchanger withdrawal error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to process your withdrawal.\n\n"
                        "**What to do:**\n"
                        "> • Make sure you have enough free funds\n"
                        "> • Check the destination address is correct\n"
                        "> • Contact support if the problem persists"
                    )
                ),
                ephemeral=True
            )

