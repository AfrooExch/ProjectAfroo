"""
Admin Exchanger Management Handler
Display and manage all exchangers, their deposits, balances, and stats
HEAD ADMIN & ASSISTANT ADMIN
"""

import logging
import discord
from discord.ui import View, Button, Modal, InputText
from typing import Optional

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, WARNING, ERROR_RED
from config import Config

logger = logging.getLogger(__name__)


async def show_exchanger_management(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Display exchanger management overview

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get all exchangers
        exchangers_data = await api.get(
            "/api/v1/admin/users/exchangers?limit=100",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        exchangers = exchangers_data.get("exchangers", [])
        total_count = exchangers_data.get("total", 0)

        # Calculate totals
        total_balance_usd = sum(e.get("total_balance_usd", 0) for e in exchangers)
        total_held_usd = sum(e.get("total_held_usd", 0) for e in exchangers)
        total_fee_reserved_usd = sum(e.get("fee_reserved_usd", 0) for e in exchangers)

        # Build exchanger list
        exchanger_list = ""
        for i, exchanger in enumerate(exchangers[:10], 1):  # Show first 10
            discord_id = exchanger.get("discord_id", "Unknown")
            username = exchanger.get("username", "Unknown")
            balance = exchanger.get("total_balance_usd", 0)
            held = exchanger.get("total_held_usd", 0)
            fee_reserved = exchanger.get("fee_reserved_usd", 0)

            exchanger_list += (
                f"{i}. **{username}** (`{discord_id}`)\n"
                f"> • Balance: `${balance:,.2f}` | Held: `${held:,.2f}` | Fee Reserve: `${fee_reserved:,.2f}`\n"
            )

        if total_count > 10:
            exchanger_list += f"\n*+{total_count - 10} more exchangers*\n"

        embed = create_themed_embed(
            title="",
            description=(
                f"## 💼 Exchanger Management\n\n"
                f"### Overview\n\n"
                f"**Total Exchangers:** {total_count}\n"
                f"**Total Balance (All):** `${total_balance_usd:,.2f} USD`\n"
                f"**Total Held Funds:** `${total_held_usd:,.2f} USD`\n"
                f"**Total Fee Reserved:** `${total_fee_reserved_usd:,.2f} USD`\n\n"
                f"### Active Exchangers\n\n"
                f"{exchanger_list if exchanger_list else '> No exchangers found'}\n"
                f"### Actions\n\n"
                f"> • Use **Search Exchanger** to view detailed exchanger info\n"
                f"> • Use **View All Deposits** to see all deposit balances\n"
                f"> • View individual exchanger wallets and private keys\n"
            ),
            color=PURPLE_GRADIENT
        )

        view = ExchangerManagementView(bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed exchanger management to admin {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error loading exchanger data: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Exchanger Data",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing exchanger management: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load exchanger data: {str(e)}"
            ),
            ephemeral=True
        )


class ExchangerManagementView(View):
    """View with buttons for exchanger management actions"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Search Exchanger",
        style=discord.ButtonStyle.primary,
        emoji="🔍"
    )
    async def search_exchanger_button(self, button: Button, interaction: discord.Interaction):
        """Search for specific exchanger"""
        modal = SearchExchangerModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="View All Deposits",
        style=discord.ButtonStyle.secondary,
        emoji=""
    )
    async def view_deposits_button(self, button: Button, interaction: discord.Interaction):
        """View all exchanger deposits breakdown"""
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get all exchangers with deposits
            exchangers_data = await api.get(
                "/api/v1/admin/users/exchangers?limit=100",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            exchangers = exchangers_data.get("exchangers", [])

            # Build deposits breakdown
            deposits_text = ""
            for exchanger in exchangers[:15]:  # Show first 15
                username = exchanger.get("username", "Unknown")
                deposits = exchanger.get("deposits", {})

                if not deposits:
                    continue

                deposits_text += f"### {username}\n\n"
                for currency, amount in deposits.items():
                    if amount > 0:
                        deposits_text += f"> • **{currency}**: `{amount:.8f}`\n"
                deposits_text += "\n"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## All Exchanger Deposits\n\n"
                    f"{deposits_text if deposits_text else '> No deposits found'}"
                ),
                color=SUCCESS_GREEN
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"API error loading deposits: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Loading Deposits",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error loading deposits: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to load deposits: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.secondary,
        emoji=""
    )
    async def refresh_button(self, button: Button, interaction: discord.Interaction):
        """Refresh exchanger list"""
        await interaction.response.defer(ephemeral=True)
        await show_exchanger_management(interaction, self.bot)


class SearchExchangerModal(Modal):
    """Modal for searching specific exchanger"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🔍 Search Exchanger")
        self.bot = bot

        self.add_item(InputText(
            label="Discord ID or Username",
            placeholder="Enter exchanger Discord ID or username",
            required=True,
            style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            search_query = self.children[0].value.strip()

            # Try to get user by discord_id or username
            user = None
            try:
                # Try as discord ID first
                user = await api.get(
                    f"/api/v1/admin/users/{search_query}",
                    discord_user_id=str(interaction.user.id),
                    discord_roles=roles
                )
            except:
                # Try as username
                all_exchangers = await api.get(
                    "/api/v1/admin/users/exchangers?limit=1000",
                    discord_user_id=str(interaction.user.id),
                    discord_roles=roles
                )

                for exchanger in all_exchangers.get("exchangers", []):
                    if exchanger.get("username", "").lower() == search_query.lower():
                        user = exchanger
                        break

            if not user:
                await interaction.followup.send(
                    embed=create_error_embed(
                        title="Exchanger Not Found",
                        description=f"No exchanger found with ID or username: `{search_query}`"
                    ),
                    ephemeral=True
                )
                return

            # Check if user is actually an exchanger
            roles = [r.lower() for r in user.get("roles", [])]
            if "exchanger" not in roles:
                await interaction.followup.send(
                    embed=create_error_embed(
                        title="Not an Exchanger",
                        description=f"User `{user.get('username')}` is not an exchanger."
                    ),
                    ephemeral=True
                )
                return

            # Build exchanger details embed
            discord_id = user.get("discord_id", "Unknown")
            username = user.get("username", "Unknown")
            total_balance = user.get("total_balance_usd", 0)
            total_held = user.get("total_held_usd", 0)
            fee_reserved = user.get("fee_reserved_usd", 0)

            deposits = user.get("deposits", {})
            deposits_text = ""
            if deposits:
                for currency, amount in deposits.items():
                    if amount > 0:
                        deposits_text += f"> • **{currency}**: `{amount:.8f}`\n"
            else:
                deposits_text = "> • No deposits\n"

            # Get stats
            stats = user.get("stats", {})
            total_exchanges = stats.get("total_exchanges", 0)
            completed_exchanges = stats.get("completed_exchanges", 0)
            total_volume = stats.get("total_volume_usd", 0)
            reputation = stats.get("reputation_score", 0)

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 💼 Exchanger Details\n\n"
                    f"### User Info\n\n"
                    f"**Username:** {username}\n"
                    f"**Discord ID:** `{discord_id}`\n"
                    f"**Status:** {user.get('status', 'active').title()}\n\n"
                    f"### Balances\n\n"
                    f"**Total Balance:** `${total_balance:,.2f} USD`\n"
                    f"**Held Funds:** `${total_held:,.2f} USD`\n"
                    f"**Fee Reserved:** `${fee_reserved:,.2f} USD`\n\n"
                    f"### Deposits by Currency\n\n"
                    f"{deposits_text}\n"
                    f"### Statistics\n\n"
                    f"**Total Exchanges:** {total_exchanges}\n"
                    f"**Completed:** {completed_exchanges}\n"
                    f"**Total Volume:** `${total_volume:,.2f} USD`\n"
                    f"**Reputation:** {reputation}/100\n\n"
                    f"### Actions\n\n"
                    f"> • Use buttons below to manage this exchanger\n"
                ),
                color=SUCCESS_GREEN
            )

            view = ExchangerDetailsView(self.bot, discord_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            logger.info(f"Admin {interaction.user.id} searched exchanger {discord_id}")

        except APIError as e:
            logger.error(f"API error searching exchanger: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Searching Exchanger",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error searching exchanger: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to search exchanger: {str(e)}"
                ),
                ephemeral=True
            )


class ExchangerDetailsView(View):
    """View with buttons for individual exchanger management"""

    def __init__(self, bot: discord.Bot, exchanger_discord_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.exchanger_discord_id = exchanger_discord_id

    @discord.ui.button(
        label="View Wallets",
        style=discord.ButtonStyle.primary,
        emoji="💳"
    )
    async def view_wallets_button(self, button: Button, interaction: discord.Interaction):
        """View exchanger wallet addresses"""
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get user wallets
            user = await api.get(
                f"/api/v1/admin/users/{self.exchanger_discord_id}",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            wallets = user.get("wallets", [])

            wallet_text = ""
            if wallets:
                for wallet in wallets:
                    currency = wallet.get("currency", "Unknown")
                    address = wallet.get("address", "N/A")
                    balance = wallet.get("balance", 0)

                    wallet_text += (
                        f"### {currency}\n\n"
                        f"**Address:** `{address}`\n"
                        f"**Balance:** `{balance:.8f} {currency}`\n\n"
                    )
            else:
                wallet_text = "> No wallets found"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 💳 Exchanger Wallets\n\n"
                    f"**User:** {user.get('username')}\n"
                    f"**Discord ID:** `{self.exchanger_discord_id}`\n\n"
                    f"{wallet_text}"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"API error loading wallets: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Loading Wallets",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error loading wallets: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to load wallets: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="View Private Keys",
        style=discord.ButtonStyle.danger,
        emoji="🔑"
    )
    async def view_private_keys_button(self, button: Button, interaction: discord.Interaction):
        """View exchanger private keys (HEAD ADMIN ONLY)"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                embed=create_error_embed(
                    title="Access Denied",
                    description="Only Head Admin can view private keys."
                ),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get user wallets with private keys
            user = await api.get(
                f"/api/v1/admin/users/{self.exchanger_discord_id}",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            wallets = user.get("wallets", [])

            keys_text = ""
            if wallets:
                for wallet in wallets:
                    currency = wallet.get("currency", "Unknown")
                    encrypted_key = wallet.get("encrypted_private_key", "N/A")

                    keys_text += (
                        f"### {currency}\n\n"
                        f"**Encrypted Key:** ||`{encrypted_key}`||\n\n"
                    )
            else:
                keys_text = "> No wallets found"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔑 Private Keys (ENCRYPTED)\n\n"
                    f"**SECURITY WARNING**\n"
                    f"> • These keys are encrypted with Fernet AES-256\n"
                    f"> • Never share keys with unauthorized personnel\n"
                    f"> • Access is being logged\n\n"
                    f"**User:** {user.get('username')}\n"
                    f"**Discord ID:** `{self.exchanger_discord_id}`\n\n"
                    f"{keys_text}"
                ),
                color=ERROR_RED
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"HEAD ADMIN {interaction.user.id} accessed private keys for exchanger {self.exchanger_discord_id}"
            )

        except APIError as e:
            logger.error(f"API error loading private keys: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Loading Private Keys",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error loading private keys: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to load private keys: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="View Active Tickets",
        style=discord.ButtonStyle.secondary,
        emoji="🎫"
    )
    async def view_tickets_button(self, button: Button, interaction: discord.Interaction):
        """View exchanger's active tickets"""
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get tickets where this exchanger is assigned
            tickets_data = await api.get(
                f"/api/v1/admin/tickets/all?limit=100",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            all_tickets = tickets_data.get("tickets", [])
            exchanger_tickets = [
                t for t in all_tickets
                if t.get("exchanger_id") == self.exchanger_discord_id
            ]

            tickets_text = ""
            if exchanger_tickets:
                for ticket in exchanger_tickets[:10]:
                    ticket_id = ticket.get("_id", "Unknown")
                    ticket_type = ticket.get("ticket_type", "Unknown")
                    status = ticket.get("status", "Unknown")
                    amount = ticket.get("amount", 0)

                    tickets_text += (
                        f"> • **{ticket_type.upper()}** | ID: `{ticket_id}` | "
                        f"Status: {status.title()} | Amount: ${amount:,.2f}\n"
                    )
            else:
                tickets_text = "> No active tickets"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🎫 Exchanger Active Tickets\n\n"
                    f"**Discord ID:** `{self.exchanger_discord_id}`\n"
                    f"**Active Tickets:** {len(exchanger_tickets)}\n\n"
                    f"{tickets_text}"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"API error loading tickets: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Loading Tickets",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error loading tickets: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to load tickets: {str(e)}"
                ),
                ephemeral=True
            )
