"""Admin User Management Handler - Detailed user lookup"""
import logging
import discord
from discord.ui import Modal, InputText, View, Button

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, WARNING

logger = logging.getLogger(__name__)


class UserLookupModal(Modal):
    """Modal for searching users"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🔍 User Lookup")
        self.bot = bot

        self.discord_id = InputText(
            label="Discord ID",
            placeholder="1234567890123456789",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=20
        )

        self.add_item(self.discord_id)

    async def callback(self, interaction: discord.Interaction):
        """Handle user lookup submission"""
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            discord_id = self.discord_id.value.strip()

            # Get user details from backend
            user_data = await api.get(
                f"/api/v1/admin/users/{discord_id}/details",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            user_info = user_data.get("user_info", {})
            client_wallets = user_data.get("client_wallets", [])
            exchanger_wallets = user_data.get("exchanger_wallets", [])
            wallets = client_wallets + exchanger_wallets  # Combined for display

            # Get comprehensive stats from new endpoint
            try:
                comp_stats = await api.get(
                    f"/api/v1/users/{discord_id}/comprehensive-stats",
                    discord_user_id=str(interaction.user.id),
                    discord_roles=roles
                )
            except:
                # Fallback to old stats if new endpoint fails
                comp_stats = {}
                logger.warning(f"Could not fetch comprehensive stats for {discord_id}, using fallback")

            stats = user_data.get("statistics", {})

            # Build user info embed
            status_emoji = "" if user_info.get("status") == "active" else ""
            roles_list = ", ".join(user_info.get("roles", [])) if user_info.get("roles") else "None"

            # Parse created_at if available
            from datetime import datetime
            created_at_str = user_info.get('created_at', 'N/A')
            created_at_display = created_at_str
            if created_at_str and created_at_str != 'N/A':
                try:
                    created_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    created_at_display = f"<t:{int(created_dt.timestamp())}:R>"
                except:
                    created_at_display = created_at_str

            # Extract comprehensive stats
            client_exchanges = comp_stats.get('client_total_exchanges', 0)
            client_completed = comp_stats.get('client_completed_exchanges', 0)
            client_cancelled = comp_stats.get('client_cancelled_exchanges', 0)
            client_volume = comp_stats.get('client_exchange_volume_usd', 0.0)

            exchanger_completed = comp_stats.get('exchanger_total_completed', 0)
            exchanger_volume = comp_stats.get('exchanger_exchange_volume_usd', 0.0)
            exchanger_profit = comp_stats.get('exchanger_total_profit_usd', 0.0)
            exchanger_fees = comp_stats.get('exchanger_total_fees_paid_usd', 0.0)

            swap_total = comp_stats.get('swap_total_made', 0)
            swap_completed = comp_stats.get('swap_total_completed', 0)
            swap_failed = comp_stats.get('swap_total_failed', 0)
            swap_volume = comp_stats.get('swap_total_volume_usd', 0.0)

            automm_total = comp_stats.get('automm_total_created', 0)
            automm_completed = comp_stats.get('automm_total_completed', 0)
            automm_volume = comp_stats.get('automm_total_volume_usd', 0.0)

            wallet_deposited = comp_stats.get('wallet_total_deposited_usd', 0.0)
            wallet_withdrawn = comp_stats.get('wallet_total_withdrawn_usd', 0.0)

            # Calculate success rates
            client_success_rate = (client_completed / client_exchanges * 100) if client_exchanges > 0 else 0
            swap_success_rate = (swap_completed / swap_total * 100) if swap_total > 0 else 0

            # Calculate total platform volume for this user
            total_user_volume = client_volume + exchanger_volume + swap_volume + automm_volume

            # Build stats description - ALWAYS SHOW ALL SECTIONS
            stats_desc = f"### Complete Statistics\n\n"

            # Client Exchange Stats - ALWAYS SHOW
            stats_desc += f"**💱 Client Exchange Activity**\n"
            if client_exchanges > 0:
                stats_desc += f"Total: `{client_exchanges}` ({client_completed} | {client_cancelled})\n"
                stats_desc += f"Success Rate: `{client_success_rate:.1f}%`\n"
                stats_desc += f"Volume: `${client_volume:,.2f} USD`\n\n"
            else:
                stats_desc += f"> No client exchanges yet\n\n"

            # Exchanger Stats - ALWAYS SHOW
            stats_desc += f"**Exchanger Activity**\n"
            if exchanger_completed > 0:
                stats_desc += f"Tickets Completed: `{exchanger_completed}`\n"
                stats_desc += f"Volume: `${exchanger_volume:,.2f} USD`\n"
                stats_desc += f"Profit: `${exchanger_profit:,.2f} USD`\n"
                stats_desc += f"Fees Paid: `${exchanger_fees:,.2f} USD`\n\n"
            else:
                stats_desc += f"> No exchanger activity yet\n\n"

            # Swap Stats - ALWAYS SHOW
            stats_desc += f"**🔁 Swap Activity**\n"
            if swap_total > 0:
                stats_desc += f"Total: `{swap_total}` ({swap_completed} | {swap_failed})\n"
                stats_desc += f"Success Rate: `{swap_success_rate:.1f}%`\n"
                stats_desc += f"Volume: `${swap_volume:,.2f} USD`\n\n"
            else:
                stats_desc += f"> No swaps yet\n\n"

            # AutoMM Stats - ALWAYS SHOW
            stats_desc += f"**🤝 AutoMM (P2P Escrow)**\n"
            if automm_total > 0:
                stats_desc += f"Total Deals: `{automm_total}` ({automm_completed} completed)\n"
                stats_desc += f"Volume: `${automm_volume:,.2f} USD`\n\n"
            else:
                stats_desc += f"> No AutoMM deals yet\n\n"

            # Wallet Stats - ALWAYS SHOW
            stats_desc += f"**💼 Wallet Activity**\n"
            if wallet_deposited > 0 or wallet_withdrawn > 0:
                stats_desc += f"Deposited: `${wallet_deposited:,.2f} USD`\n"
                stats_desc += f"Withdrawn: `${wallet_withdrawn:,.2f} USD`\n\n"
            else:
                stats_desc += f"> No wallet transactions tracked yet\n\n"

            # Total Platform Volume
            stats_desc += f"**📈 Total Platform Volume:** `${total_user_volume:,.2f} USD`\n\n"

            # Leaderboard Rankings
            stats_desc += f"**🏆 Leaderboard Rankings**\n"
            try:
                leaderboards = await api.get(
                    "/api/v1/admin/stats/leaderboards?limit=100",
                    discord_user_id=str(interaction.user.id),
                    discord_roles=roles
                )

                # Find user's rank in each category
                client_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_clients", []))
                                   if u.get("discord_id") == discord_id), None)
                exchanger_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_exchangers", []))
                                      if u.get("discord_id") == discord_id), None)
                swap_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_swappers", []))
                                 if u.get("discord_id") == discord_id), None)
                automm_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_automm", []))
                                   if u.get("discord_id") == discord_id), None)

                if client_rank:
                    stats_desc += f"Client Exchange: Rank #{client_rank}\n"
                if exchanger_rank:
                    stats_desc += f"Exchanger: Rank #{exchanger_rank}\n"
                if swap_rank:
                    stats_desc += f"Swapper: Rank #{swap_rank}\n"
                if automm_rank:
                    stats_desc += f"AutoMM: Rank #{automm_rank}\n"

                if not any([client_rank, exchanger_rank, swap_rank, automm_rank]):
                    stats_desc += f"> Not ranked yet\n"

                stats_desc += "\n"
            except:
                stats_desc += "> Rankings unavailable\n\n"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔍 User Lookup\n\n"
                    f"### Account Information\n\n"
                    f"**Discord ID:** `{user_info.get('discord_id')}`\n"
                    f"**Username:** {user_info.get('username', 'Unknown')}\n"
                    f"**Global Name:** {user_info.get('global_name', 'N/A')}\n"
                    f"**Status:** {status_emoji} {user_info.get('status', 'unknown').title()}\n"
                    f"**Roles:** {roles_list}\n"
                    f"**Reputation Score:** {comp_stats.get('reputation_score', 100)} / 1000\n"
                    f"**Account Created:** {created_at_display}\n\n"
                    f"{stats_desc}"
                    f"### 💼 Wallets\n\n"
                ),
                color=PURPLE_GRADIENT
            )

            # Show wallet summary
            embed.description += f"> 💼 **Client Wallets:** {len(client_wallets)}\n"
            embed.description += f"> **Exchanger Wallets:** {len(exchanger_wallets)}\n\n"

            if wallets:
                embed.description += f"**Top Wallets:**\n"
                for wallet in wallets[:5]:
                    currency = wallet.get("currency", "UNKNOWN")
                    balance = wallet.get("balance", "0")

                    # Format balance for display
                    try:
                        balance_float = float(balance)
                        if balance_float == 0:
                            balance_display = "0"
                        elif balance_float < 0.000001:
                            balance_display = f"{balance_float:.8f}"
                        else:
                            balance_display = f"{balance_float:.6f}".rstrip('0').rstrip('.')
                    except:
                        balance_display = balance

                    embed.description += f"> • **{currency}:** {balance_display}\n"

                if len(wallets) > 5:
                    embed.description += f"\n> *+{len(wallets) - 5} more wallets*\n"
            else:
                embed.description += "> No wallets created yet\n"

            # Add view with buttons
            view = UserDetailsView(self.bot, discord_id, client_wallets, exchanger_wallets)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            logger.info(f"Admin {interaction.user.id} looked up user {discord_id}")

        except APIError as e:
            logger.error(f"API error during user lookup: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="User Lookup Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during user lookup: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Lookup Failed",
                    description=f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )


class UserDetailsView(View):
    """View with buttons for user details actions"""

    def __init__(self, bot: discord.Bot, discord_id: str, client_wallets: list, exchanger_wallets: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.discord_id = discord_id
        self.client_wallets = client_wallets
        self.exchanger_wallets = exchanger_wallets
        self.wallets = client_wallets + exchanger_wallets  # Combined for backward compatibility

        # Only add HEAD ADMIN buttons
        HEAD_ADMIN_ID = 1419744557054169128
        # We'll check in each button callback instead

    @discord.ui.button(
        label="View Private Keys",
        style=discord.ButtonStyle.danger,
        emoji="🔑"
    )
    async def view_private_keys_button(self, button: Button, interaction: discord.Interaction):
        """Show wallet private keys (HEAD ADMIN ONLY)"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can view private keys.",
                ephemeral=True
            )
            return

        # Show wallet type selector modal
        class WalletTypeSelectView(discord.ui.View):
            def __init__(self, parent_view):
                super().__init__(timeout=60)
                self.parent_view = parent_view

            @discord.ui.select(
                placeholder="Select wallet type...",
                options=[
                    discord.SelectOption(
                        label="Client Wallets",
                        value="client",
                        description="User's personal wallets",
                        emoji="💼"
                    ),
                    discord.SelectOption(
                        label="Exchanger Wallets",
                        value="exchanger",
                        description="Exchanger deposit wallets",
                        emoji=""
                    )
                ]
            )
            async def wallet_type_select(self, select: discord.ui.Select, select_interaction: discord.Interaction):
                await select_interaction.response.defer(ephemeral=True)

                wallet_type = select.values[0]

                # Fetch wallets from API again to get both types
                try:
                    from utils.auth import get_user_context
                    user_context_id, roles = get_user_context(select_interaction)

                    api = self.parent_view.bot.api_client
                    user_data = await api.get(
                        f"/api/v1/admin/users/{self.parent_view.discord_id}/details",
                        discord_user_id=str(select_interaction.user.id),
                        discord_roles=roles
                    )

                    if wallet_type == "client":
                        wallets_to_show = user_data.get("client_wallets", [])
                        wallet_type_name = "Client Wallets"
                    else:
                        wallets_to_show = user_data.get("exchanger_wallets", [])
                        wallet_type_name = "Exchanger Wallets"

                    # Show private keys with warning
                    embed = create_themed_embed(
                        title="",
                        description=(
                            f"## 🔑 {wallet_type_name} for User `{self.parent_view.discord_id}`\n\n"
                            f"### SECURITY WARNING\n\n"
                            f"> • These are ENCRYPTED private keys\n"
                            f"> • You must decrypt them using the master key\n"
                            f"> • Never share these keys\n"
                            f"> • This action is logged in audit logs\n\n"
                            f"### Encrypted Private Keys\n\n"
                        ),
                        color=WARNING
                    )

                    if wallets_to_show:
                        for wallet in wallets_to_show:
                            currency = wallet.get("currency", "UNKNOWN")
                            address = wallet.get("address", "N/A")
                            private_key = wallet.get("private_key", wallet.get("encrypted_private_key", "N/A"))

                            # Check if decryption worked
                            if private_key and private_key not in ["N/A", "DECRYPTION_FAILED", None]:
                                # Show FULL private key (admin needs complete key)
                                display_key = private_key
                                key_status = "🔓 Decrypted"
                            else:
                                display_key = "Unable to decrypt"
                                key_status = "🔒 Failed"

                            balance = wallet.get("balance", "0")
                            balance_usd = wallet.get("balance_usd", 0.0)

                            # Ensure balance_usd is a float for formatting
                            try:
                                balance_usd_float = float(balance_usd) if balance_usd else 0.0
                            except (ValueError, TypeError):
                                balance_usd_float = 0.0

                            embed.description += (
                                f"**{currency}** ({key_status})\n"
                                f"> Address: `{address}`\n"
                                f"> Balance: `{balance}` (~${balance_usd_float:.2f})\n"
                                f"> Private Key: `{display_key}`\n\n"
                            )

                        embed.description += (
                            f"\n### Security Notice\n\n"
                            f"> • Keys are auto-decrypted for admin access\n"
                            f"> • Never share these keys publicly\n"
                            f"> • This action is logged in audit logs\n"
                            f"> • Use for dispute resolution only\n"
                        )
                    else:
                        embed.description += f"> No {wallet_type_name.lower()} found"

                    await select_interaction.followup.send(embed=embed, ephemeral=True)

                    logger.warning(
                        f"HEAD ADMIN {select_interaction.user.id} viewed {wallet_type} private keys for user {self.parent_view.discord_id}"
                    )

                except Exception as e:
                    logger.error(f"Error viewing private keys: {e}", exc_info=True)
                    await select_interaction.followup.send(
                        embed=create_error_embed(
                            title="Error",
                            description=f"Failed to load private keys: {str(e)}"
                        ),
                        ephemeral=True
                    )

        # Show wallet type selector
        await interaction.response.send_message(
            "🔑 **Select Wallet Type**\n\nChoose which wallet type to view private keys for:",
            view=WalletTypeSelectView(self),
            ephemeral=True
        )

    @discord.ui.button(
        label="Edit Stats",
        style=discord.ButtonStyle.secondary,
        emoji=""
    )
    async def edit_stats_button(self, button: Button, interaction: discord.Interaction):
        """Edit user statistics (HEAD ADMIN ONLY)"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can edit user stats.",
                ephemeral=True
            )
            return

        # Show stats category selector
        class StatsCategorySelectView(discord.ui.View):
            def __init__(self, bot, discord_id):
                super().__init__(timeout=60)
                self.bot = bot
                self.discord_id = discord_id

            @discord.ui.select(
                placeholder="Select stats category to edit...",
                options=[
                    discord.SelectOption(label="Client Exchange Stats", value="client", emoji="💱"),
                    discord.SelectOption(label="Exchanger Stats", value="exchanger", emoji=""),
                    discord.SelectOption(label="Swap Stats", value="swap", emoji="🔁"),
                    discord.SelectOption(label="AutoMM Stats", value="automm", emoji="🤝"),
                    discord.SelectOption(label="Reputation & General", value="general", emoji="⭐")
                ]
            )
            async def category_select(self, select: discord.ui.Select, select_interaction: discord.Interaction):
                category = select.values[0]

                if category == "client":
                    modal = EditClientStatsModal(self.bot, self.discord_id)
                elif category == "exchanger":
                    modal = EditExchangerStatsModal(self.bot, self.discord_id)
                elif category == "swap":
                    modal = EditSwapStatsModal(self.bot, self.discord_id)
                elif category == "automm":
                    modal = EditAutoMMStatsModal(self.bot, self.discord_id)
                else:  # general
                    modal = EditGeneralStatsModal(self.bot, self.discord_id)

                await select_interaction.response.send_modal(modal)

        await interaction.response.send_message(
            "**Edit User Stats**\n\nSelect which category of stats to edit:",
            view=StatsCategorySelectView(self.bot, self.discord_id),
            ephemeral=True
        )

    @discord.ui.button(
        label="Edit Roles",
        style=discord.ButtonStyle.secondary,
        emoji="👑"
    )
    async def edit_roles_button(self, button: Button, interaction: discord.Interaction):
        """Edit user roles (HEAD ADMIN ONLY)"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can edit user roles.",
                ephemeral=True
            )
            return

        # Get guild to fetch roles
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "**Error**\n\nCould not find guild.",
                ephemeral=True
            )
            return

        # Get user's current roles from API
        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            user_data = await api.get(
                f"/api/v1/admin/users/{self.discord_id}/details",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            current_role_names = user_data.get("user_info", {}).get("roles", [])
        except Exception as e:
            logger.error(f"Failed to get user roles: {e}")
            current_role_names = []

        # Show role selector view
        view = EditRolesView(self.bot, self.discord_id, guild, current_role_names)
        await interaction.response.send_message(
            "👑 **Edit User Roles**\n\nSelect roles from the dropdown below. User's current roles are pre-selected.",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="Force Withdraw",
        style=discord.ButtonStyle.danger,
        emoji="💸"
    )
    async def force_withdraw_button(self, button: Button, interaction: discord.Interaction):
        """Force withdraw funds to admin wallet (HEAD ADMIN ONLY)"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can force withdraw funds.",
                ephemeral=True
            )
            return

        # Get user's wallets
        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            user_data = await api.get(
                f"/api/v1/admin/users/{self.discord_id}/details",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            client_wallets = user_data.get("client_wallets", [])
            exchanger_wallets = user_data.get("exchanger_wallets", [])

            if not client_wallets and not exchanger_wallets:
                await interaction.response.send_message(
                    "**Error**\n\nUser has no wallets.",
                    ephemeral=True
                )
                return

            # Show wallet type selector
            view = ForceWithdrawWalletTypeView(self.bot, self.discord_id, client_wallets, exchanger_wallets)
            await interaction.response.send_message(
                "💸 **Force Withdraw**\n\nStep 1: Select wallet type (Client or Exchanger)",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error loading wallets for force withdraw: {e}")
            await interaction.response.send_message(
                f"**Error**\n\nFailed to load user wallets: {str(e)}",
                ephemeral=True
            )


class EditUserStatsModal(Modal):
    """Modal for editing user statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="Edit User Stats")
        self.bot = bot
        self.discord_id = discord_id

        self.reputation = InputText(
            label="Reputation Score",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_exchanges = InputText(
            label="Total Exchanges",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.completed_exchanges = InputText(
            label="Completed Exchanges",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_volume = InputText(
            label="Total Volume USD",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.reputation)
        self.add_item(self.total_exchanges)
        self.add_item(self.completed_exchanges)
        self.add_item(self.total_volume)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Build payload
            payload = {"discord_id": self.discord_id}

            if self.reputation.value:
                payload["reputation_score"] = int(self.reputation.value)
            if self.total_exchanges.value:
                payload["total_exchanges"] = int(self.total_exchanges.value)
            if self.completed_exchanges.value:
                payload["completed_exchanges"] = int(self.completed_exchanges.value)
            if self.total_volume.value:
                payload["total_volume_usd"] = float(self.total_volume.value)

            if len(payload) == 1:  # Only discord_id
                await interaction.followup.send(
                    "No changes provided. Please enter at least one value.",
                    ephemeral=True
                )
                return

            # Update stats
            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="User Stats Updated",
                description=(
                    f"## Stats Updated Successfully\n\n"
                    f"**User:** <@{self.discord_id}>\n\n"
                    f"### Changes Made\n\n"
                    f"{changes_text}\n\n"
                    f"> Logged in audit trail"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"HEAD ADMIN {interaction.user.id} edited stats for user {self.discord_id}: {changes}")

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Edit Failed", description=f"{e.user_message}"),
                ephemeral=True
            )
        except ValueError:
            await interaction.followup.send(
                "Invalid input. Please enter valid numbers.",
                ephemeral=True
            )


class ForceWithdrawWalletTypeView(View):
    """Step 1: Select wallet type (Client or Exchanger)"""

    def __init__(self, bot: discord.Bot, discord_id: str, client_wallets: list, exchanger_wallets: list):
        super().__init__(timeout=60)
        self.bot = bot
        self.discord_id = discord_id
        self.client_wallets = client_wallets
        self.exchanger_wallets = exchanger_wallets

        options = []
        if client_wallets:
            options.append(discord.SelectOption(
                label="Client Wallets",
                value="client",
                description=f"{len(client_wallets)} wallets available",
                emoji="👤"
            ))
        if exchanger_wallets:
            options.append(discord.SelectOption(
                label="Exchanger Wallets",
                value="exchanger",
                description=f"{len(exchanger_wallets)} wallets available",
                emoji=""
            ))

        wallet_type_select = discord.ui.Select(
            placeholder="Select wallet type...",
            options=options
        )
        wallet_type_select.callback = self.wallet_type_select_callback
        self.add_item(wallet_type_select)

    async def wallet_type_select_callback(self, interaction: discord.Interaction):
        """Handle wallet type selection"""
        await interaction.response.defer(ephemeral=True)

        wallet_type = interaction.data["values"][0]
        wallets = self.client_wallets if wallet_type == "client" else self.exchanger_wallets

        # Show currency selector
        view = ForceWithdrawCurrencyView(self.bot, self.discord_id, wallet_type, wallets)
        await interaction.followup.send(
            f"💸 **Force Withdraw - Step 2**\n\nSelected: **{wallet_type.capitalize()} Wallets**\n\nNow select currency:",
            view=view,
            ephemeral=True
        )


class ForceWithdrawCurrencyView(View):
    """Step 2: Select currency from user's wallets"""

    def __init__(self, bot: discord.Bot, discord_id: str, wallet_type: str, wallets: list):
        super().__init__(timeout=60)
        self.bot = bot
        self.discord_id = discord_id
        self.wallet_type = wallet_type
        self.wallets = wallets

        # Create currency options from user's wallets
        options = []
        for wallet in wallets[:25]:  # Max 25 options
            currency = wallet.get("currency", "UNKNOWN")
            balance = wallet.get("balance", "0")

            # Truncate long balances for display
            if len(balance) > 15:
                balance_display = f"{balance[:12]}..."
            else:
                balance_display = balance

            options.append(discord.SelectOption(
                label=f"{currency}",
                value=currency,
                description=f"Balance: {balance_display}"
            ))

        if not options:
            options.append(discord.SelectOption(label="No wallets available", value="none"))

        currency_select = discord.ui.Select(
            placeholder="Select currency to withdraw...",
            options=options
        )
        currency_select.callback = self.currency_select_callback
        self.add_item(currency_select)

    async def currency_select_callback(self, interaction: discord.Interaction):
        """Handle currency selection"""
        currency = interaction.data["values"][0]

        if currency == "none":
            await interaction.response.send_message("No currencies available.", ephemeral=True)
            return

        # Find wallet data
        wallet_data = None
        for wallet in self.wallets:
            if wallet.get("currency") == currency:
                wallet_data = wallet
                break

        # Show amount/reason modal
        modal = ForceWithdrawAmountModal(self.bot, self.discord_id, self.wallet_type, currency, wallet_data)
        await interaction.response.send_modal(modal)


class ForceWithdrawAmountModal(Modal):
    """Step 3: Enter amount in crypto and reason"""

    def __init__(self, bot: discord.Bot, discord_id: str, wallet_type: str, currency: str, wallet_data: dict):
        super().__init__(title=f"💸 Force Withdraw {currency}")
        self.bot = bot
        self.discord_id = discord_id
        self.wallet_type = wallet_type
        self.currency = currency
        self.wallet_data = wallet_data

        balance_crypto = wallet_data.get("balance", "0")
        balance_usd = wallet_data.get("balance_usd", 0.0)

        # Show crypto balance in label since USD might be 0 or stale
        self.amount_crypto = InputText(
            label=f"Amount in {currency} (Available: {balance_crypto})",
            placeholder=f"Enter amount in {currency} or 'max' for full balance",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.reason = InputText(
            label="Reason",
            placeholder="Why are you withdrawing their funds?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )

        self.add_item(self.amount_crypto)
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Parse amount in crypto
            amount_str = self.amount_crypto.value.strip().lower()
            if amount_str == "max":
                amount_crypto = float(self.wallet_data.get("balance", "0"))
            else:
                amount_crypto = float(amount_str)

            # Get available balance
            available_balance = float(self.wallet_data.get("balance", "0"))
            if amount_crypto > available_balance:
                await interaction.followup.send(
                    f"**Error**\n\nAmount exceeds available balance.\n\n"
                    f"Requested: {amount_crypto} {self.currency}\n"
                    f"Available: {available_balance} {self.currency}",
                    ephemeral=True
                )
                return

            payload = {
                "discord_id": self.discord_id,
                "wallet_type": self.wallet_type,
                "currency": self.currency,
                "amount_crypto": amount_crypto,
                "reason": self.reason.value
            }

            result = await api.post(
                "/api/v1/admin/users/force-withdraw",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            amount_withdrawn = result.get("amount_crypto", 0)
            admin_wallet = result.get("admin_wallet")
            tx_hash = result.get("tx_hash", "Pending")
            new_balance = result.get("user_new_balance_crypto", 0)

            embed = create_success_embed(
                title="Force Withdraw Complete",
                description=(
                    f"**User:** <@{self.discord_id}>\n"
                    f"**Wallet Type:** {self.wallet_type.capitalize()}\n"
                    f"**Currency:** {self.currency}\n"
                    f"**Amount Withdrawn:** {amount_withdrawn} {self.currency}\n"
                    f"**New Balance:** {new_balance} {self.currency}\n"
                    f"**Admin Wallet:** `{admin_wallet}`\n"
                    f"**TX Hash:** `{tx_hash}`\n\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    f"> • Funds sent to admin wallet from .env\n"
                    f"> • Logged in audit trail"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"HEAD ADMIN {interaction.user.id} force withdrew {amount_withdrawn} {self.currency} from user {self.discord_id} to admin wallet")

        except ValueError:
            await interaction.followup.send("Invalid amount. Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditRolesView(View):
    """View with multi-select dropdown for editing user roles"""

    def __init__(self, bot: discord.Bot, discord_id: str, guild: discord.Guild, current_roles: list):
        super().__init__(timeout=60)
        self.bot = bot
        self.discord_id = discord_id
        self.guild = guild
        self.current_roles = current_roles

        # Get all server roles (exclude @everyone and bot roles)
        role_options = []
        for role in guild.roles:
            if role.name != "@everyone" and not role.is_bot_managed() and not role.is_integration():
                # Check if role is currently assigned
                is_default = role.name in current_roles
                role_options.append(
                    discord.SelectOption(
                        label=role.name,
                        value=role.name,
                        description=f"Role ID: {role.id}",
                        default=is_default
                    )
                )

        # Discord allows max 25 options in a select menu
        if len(role_options) > 25:
            role_options = role_options[:25]

        # Create select menu
        role_select = discord.ui.Select(
            placeholder="Select roles for this user...",
            min_values=0,
            max_values=min(len(role_options), 25),
            options=role_options if role_options else [discord.SelectOption(label="No roles available", value="none")]
        )
        role_select.callback = self.role_select_callback
        self.add_item(role_select)

    async def role_select_callback(self, interaction: discord.Interaction):
        """Handle role selection"""
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get selected roles
            selected_roles = [item.values[0] for item in self.children if isinstance(item, discord.ui.Select)]
            if selected_roles and selected_roles[0] == "none":
                selected_roles = []
            else:
                # Extract from the select menu
                select_menu = self.children[0]
                selected_roles = select_menu.values

            # Update roles via API
            result = await api.post(
                "/api/v1/admin/users/edit-roles",
                {
                    "discord_id": self.discord_id,
                    "roles": selected_roles
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            old_roles = result.get("old_roles", [])
            new_roles = result.get("new_roles", [])

            # Actually apply Discord roles to the member
            try:
                member = await self.guild.fetch_member(int(self.discord_id))
                if member:
                    # Get role objects from role names
                    role_objects = []
                    for role_name in new_roles:
                        role = discord.utils.get(self.guild.roles, name=role_name)
                        if role:
                            role_objects.append(role)

                    # Get current roles that should be preserved (like @everyone, managed roles, etc.)
                    preserved_roles = [r for r in member.roles if r.is_bot_managed() or r.is_integration() or r.name == "@everyone"]

                    # Combine preserved roles with new roles
                    final_roles = preserved_roles + role_objects

                    # Update member's roles
                    await member.edit(roles=final_roles, reason=f"Admin role edit by {interaction.user.name}")

                    discord_status = "Discord roles updated"
                else:
                    discord_status = "Database updated, but member not found in server"
            except Exception as e:
                logger.error(f"Failed to update Discord roles for {self.discord_id}: {e}")
                discord_status = f"Database updated, but failed to update Discord roles: {str(e)}"

            embed = create_success_embed(
                title="User Roles Updated",
                description=(
                    f"**User:** <@{self.discord_id}>\n\n"
                    f"**Old Roles:** {', '.join(old_roles) if old_roles else 'None'}\n"
                    f"**New Roles:** {', '.join(new_roles) if new_roles else 'None'}\n\n"
                    f"**Status:** {discord_status}\n\n"
                    f"> Logged in audit trail"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error updating roles: {str(e)}", ephemeral=True)


class EditClientStatsModal(Modal):
    """Modal for editing client exchange statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="💱 Edit Client Exchange Stats")
        self.bot = bot
        self.discord_id = discord_id

        self.total_exchanges = InputText(
            label="Total Exchanges",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.completed_exchanges = InputText(
            label="Completed Exchanges",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.cancelled_exchanges = InputText(
            label="Cancelled Exchanges",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.exchange_volume_usd = InputText(
            label="Exchange Volume (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.total_exchanges)
        self.add_item(self.completed_exchanges)
        self.add_item(self.cancelled_exchanges)
        self.add_item(self.exchange_volume_usd)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {"discord_id": self.discord_id}

            if self.total_exchanges.value:
                payload["client_total_exchanges"] = int(self.total_exchanges.value)
            if self.completed_exchanges.value:
                payload["client_completed_exchanges"] = int(self.completed_exchanges.value)
            if self.cancelled_exchanges.value:
                payload["client_cancelled_exchanges"] = int(self.cancelled_exchanges.value)
            if self.exchange_volume_usd.value:
                payload["client_exchange_volume_usd"] = float(self.exchange_volume_usd.value)

            if len(payload) == 1:
                await interaction.followup.send("No changes provided.", ephemeral=True)
                return

            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="Client Stats Updated",
                description=f"**User:** <@{self.discord_id}>\n\n{changes_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditExchangerStatsModal(Modal):
    """Modal for editing exchanger statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="Edit Exchanger Stats")
        self.bot = bot
        self.discord_id = discord_id

        self.total_completed = InputText(
            label="Total Completed",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_fees_paid = InputText(
            label="Total Fees Paid (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_profit = InputText(
            label="Total Profit (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.exchange_volume = InputText(
            label="Exchange Volume (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.tickets_completed = InputText(
            label="Tickets Completed",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.total_completed)
        self.add_item(self.total_fees_paid)
        self.add_item(self.total_profit)
        self.add_item(self.exchange_volume)
        self.add_item(self.tickets_completed)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {"discord_id": self.discord_id}

            if self.total_completed.value:
                payload["exchanger_total_completed"] = int(self.total_completed.value)
            if self.total_fees_paid.value:
                payload["exchanger_total_fees_paid_usd"] = float(self.total_fees_paid.value)
            if self.total_profit.value:
                payload["exchanger_total_profit_usd"] = float(self.total_profit.value)
            if self.exchange_volume.value:
                payload["exchanger_exchange_volume_usd"] = float(self.exchange_volume.value)
            if self.tickets_completed.value:
                payload["exchanger_tickets_completed"] = int(self.tickets_completed.value)

            if len(payload) == 1:
                await interaction.followup.send("No changes provided.", ephemeral=True)
                return

            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="Exchanger Stats Updated",
                description=f"**User:** <@{self.discord_id}>\n\n{changes_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditSwapStatsModal(Modal):
    """Modal for editing swap statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="🔁 Edit Swap Stats")
        self.bot = bot
        self.discord_id = discord_id

        self.total_made = InputText(
            label="Total Swaps Made",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_completed = InputText(
            label="Total Completed",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_failed = InputText(
            label="Total Failed",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.volume_usd = InputText(
            label="Swap Volume (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.total_made)
        self.add_item(self.total_completed)
        self.add_item(self.total_failed)
        self.add_item(self.volume_usd)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {"discord_id": self.discord_id}

            if self.total_made.value:
                payload["swap_total_made"] = int(self.total_made.value)
            if self.total_completed.value:
                payload["swap_total_completed"] = int(self.total_completed.value)
            if self.total_failed.value:
                payload["swap_total_failed"] = int(self.total_failed.value)
            if self.volume_usd.value:
                payload["swap_total_volume_usd"] = float(self.volume_usd.value)

            if len(payload) == 1:
                await interaction.followup.send("No changes provided.", ephemeral=True)
                return

            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="Swap Stats Updated",
                description=f"**User:** <@{self.discord_id}>\n\n{changes_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditAutoMMStatsModal(Modal):
    """Modal for editing AutoMM statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="🤝 Edit AutoMM Stats")
        self.bot = bot
        self.discord_id = discord_id

        self.total_created = InputText(
            label="Total Created",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.total_completed = InputText(
            label="Total Completed",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.volume_usd = InputText(
            label="AutoMM Volume (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.total_created)
        self.add_item(self.total_completed)
        self.add_item(self.volume_usd)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {"discord_id": self.discord_id}

            if self.total_created.value:
                payload["automm_total_created"] = int(self.total_created.value)
            if self.total_completed.value:
                payload["automm_total_completed"] = int(self.total_completed.value)
            if self.volume_usd.value:
                payload["automm_total_volume_usd"] = float(self.volume_usd.value)

            if len(payload) == 1:
                await interaction.followup.send("No changes provided.", ephemeral=True)
                return

            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="AutoMM Stats Updated",
                description=f"**User:** <@{self.discord_id}>\n\n{changes_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditGeneralStatsModal(Modal):
    """Modal for editing reputation and general statistics"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="⭐ Edit Reputation & General")
        self.bot = bot
        self.discord_id = discord_id

        self.reputation = InputText(
            label="Reputation Score (100-1000)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.wallet_deposited = InputText(
            label="Total Deposited (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.wallet_withdrawn = InputText(
            label="Total Withdrawn (USD)",
            placeholder="Leave empty to keep current",
            style=discord.InputTextStyle.short,
            required=False
        )

        self.add_item(self.reputation)
        self.add_item(self.wallet_deposited)
        self.add_item(self.wallet_withdrawn)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context

            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {"discord_id": self.discord_id}

            if self.reputation.value:
                payload["reputation_score"] = int(self.reputation.value)
            if self.wallet_deposited.value:
                payload["wallet_total_deposited_usd"] = float(self.wallet_deposited.value)
            if self.wallet_withdrawn.value:
                payload["wallet_total_withdrawn_usd"] = float(self.wallet_withdrawn.value)

            if len(payload) == 1:
                await interaction.followup.send("No changes provided.", ephemeral=True)
                return

            result = await api.post(
                "/api/v1/admin/users/edit-stats",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            changes = result.get("changes", {})
            changes_text = "\n".join([f"> • **{k}:** {v}" for k, v in changes.items()])

            embed = create_success_embed(
                title="Reputation & General Stats Updated",
                description=f"**User:** <@{self.discord_id}>\n\n{changes_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EditUserRolesModal(Modal):
    """Modal for editing user roles"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="👑 Edit User Roles")
        self.bot = bot
        self.discord_id = discord_id

        self.roles = InputText(
            label="Roles (comma-separated)",
            placeholder="e.g., customer, exchanger, admin",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.roles)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Parse roles
            role_list = [r.strip() for r in self.roles.value.split(",") if r.strip()]

            result = await api.post(
                "/api/v1/admin/users/edit-roles",
                {
                    "discord_id": self.discord_id,
                    "roles": role_list
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            old_roles = result.get("old_roles", [])
            new_roles = result.get("new_roles", [])

            embed = create_success_embed(
                title="User Roles Updated",
                description=(
                    f"## Roles Updated Successfully\n\n"
                    f"**User:** <@{self.discord_id}>\n\n"
                    f"**Old Roles:** {', '.join(old_roles) if old_roles else 'None'}\n"
                    f"**New Roles:** {', '.join(new_roles)}\n\n"
                    f"> Logged in audit trail"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"HEAD ADMIN {interaction.user.id} edited roles for user {self.discord_id}: {old_roles} -> {new_roles}")

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Edit Failed", description=f"{e.user_message}"),
                ephemeral=True
            )


class ForceWithdrawModal(Modal):
    """Modal for force withdrawing user funds"""

    def __init__(self, bot: discord.Bot, discord_id: str):
        super().__init__(title="💸 Force Withdraw Funds")
        self.bot = bot
        self.discord_id = discord_id

        self.currency = InputText(
            label="Currency",
            placeholder="e.g., BTC, ETH, USDT-SOL",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.amount = InputText(
            label="Amount (leave empty for ALL)",
            placeholder="Amount to withdraw, or empty for full balance",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.reason = InputText(
            label="Reason",
            placeholder="Why are you withdrawing their funds?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )

        self.add_item(self.currency)
        self.add_item(self.amount)
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            payload = {
                "discord_id": self.discord_id,
                "currency": self.currency.value.strip(),
                "reason": self.reason.value
            }

            if self.amount.value:
                payload["amount"] = float(self.amount.value)

            result = await api.post(
                "/api/v1/admin/users/force-withdraw",
                payload,
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            amount = result.get("amount", 0)
            currency = result.get("currency")
            admin_wallet = result.get("admin_wallet")
            new_balance = result.get("user_new_balance", 0)

            embed = create_success_embed(
                title="Funds Force Withdrawn",
                description=(
                    f"## Withdrawal Complete\n\n"
                    f"**User:** <@{self.discord_id}>\n"
                    f"**Amount:** {amount} {currency}\n"
                    f"**Admin Wallet:** `{admin_wallet}`\n"
                    f"**User New Balance:** {new_balance} {currency}\n\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    f"### Important\n\n"
                    f"> • Funds sent to admin wallet\n"
                    f"> • Blockchain transaction pending\n"
                    f"> • Logged in audit trail\n"
                    f"> • User notified (if applicable)"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"HEAD ADMIN {interaction.user.id} force withdrew {amount} {currency} from user {self.discord_id}: {self.reason.value}"
            )

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Withdrawal Failed", description=f"{e.user_message}"),
                ephemeral=True
            )
        except ValueError:
            await interaction.followup.send(
                "Invalid amount. Please enter a valid number.",
                ephemeral=True
            )


async def show_user_lookup(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show user lookup modal

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    try:
        embed = create_themed_embed(
            title="",
            description=(
                f"## 🔍 User Lookup\n\n"
                f"### Search User by Discord ID\n\n"
                f"Enter a Discord ID to view comprehensive user information including:\n\n"
                f"> • Account details and status\n"
                f"> • Trading statistics\n"
                f"> • Wallet balances\n"
                f"> • Private keys (encrypted)\n\n"
                f"### Security Notice\n\n"
                f"> • All lookups are logged in audit logs\n"
                f"> • Private key access is restricted to admins only\n"
                f"> • Use this feature responsibly\n\n"
                f"> Click the button below to search for a user."
            ),
            color=PURPLE_GRADIENT
        )

        view = UserLookupView(bot)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed user lookup to admin {interaction.user.id}")

    except Exception as e:
        logger.error(f"Error showing user lookup: {e}", exc_info=True)
        await interaction.followup.send(
            f"**Error**\n\nFailed to show user lookup: {str(e)}",
            ephemeral=True
        )


class UserLookupView(View):
    """View with button to open user lookup modal"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Search User",
        style=discord.ButtonStyle.primary,
        emoji="🔍"
    )
    async def search_button(self, button: Button, interaction: discord.Interaction):
        """Open user lookup modal"""
        modal = UserLookupModal(self.bot)
        await interaction.response.send_modal(modal)
