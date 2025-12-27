"""
Exchanger Ticket View - Thread-based system
Displays Claim Ticket, Client Info, and Ask Question buttons
"""

import logging
import discord
from discord.ui import View, Button
from datetime import datetime

from config import config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED

logger = logging.getLogger(__name__)


class ExchangerTicketView(View):
    """View for exchanger thread with Claim, Client Info, and Ask Question buttons"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.Thread):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="claim_ticket_v2"
    )
    async def claim_button(self, button: Button, interaction: discord.Interaction):
        """Handle ticket claim"""
        await interaction.response.defer(ephemeral=True)

        logger.info(f"Exchanger {interaction.user.id} attempting to claim ticket #{self.ticket_id}")

        # Check if user has any exchanger role or is admin
        is_exchanger = self.has_exchanger_role(interaction.user)
        is_admin = config.is_admin(interaction.user)

        # Check specifically for Head Admin or Assistant Admin roles (for bypass)
        is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        admin_bypass = is_head_admin or is_assistant_admin

        if not is_exchanger and not is_admin:
            await interaction.followup.send(
                "❌ You need an Exchanger role to claim tickets.",
                ephemeral=True
            )
            return

        try:
            # Get user context for authentication
            user_id = str(interaction.user.id)
            roles = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []

            # Admin bypass: Head Admin & Assistant Admin can claim without deposits/holds
            # Regular exchangers must have deposits
            if admin_bypass:
                logger.info(f"Admin {interaction.user.name} claiming ticket with bypass (no deposits required)")
                result = await self.bot.api_client.post(
                    f"/api/v1/admin/tickets/force-claim",
                    data={
                        "ticket_id": self.ticket_id,
                        "exchanger_discord_id": user_id
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )
            else:
                logger.info(f"Exchanger {interaction.user.name} claiming ticket (requires fund hold)")
                result = await self.bot.api_client.post(
                    f"/api/v1/tickets/{self.ticket_id}/claim",
                    data={
                        "exchanger_id": user_id,
                        "exchanger_username": interaction.user.name
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )

            logger.info(f"Ticket #{self.ticket_id} successfully claimed by {interaction.user.name}")

            # Get ticket data to find client channel
            ticket_data = result.get("ticket") if isinstance(result, dict) else result
            logger.info(f"Claim result data: {result}")

            if not ticket_data:
                logger.error(f"No ticket data returned from claim API")
                ticket_data = {}

            client_channel_id = ticket_data.get("channel_id")
            logger.info(f"Client channel ID from ticket: {client_channel_id}")

            # If channel_id not in claim response, fetch full ticket data
            if not client_channel_id:
                logger.warning("channel_id not in claim response, fetching full ticket data")
                try:
                    full_ticket = await self.bot.api_client.get(
                        f"/api/v1/tickets/{self.ticket_id}",
                        discord_user_id=user_id,
                        discord_roles=roles
                    )
                    ticket_data = full_ticket.get("ticket") if isinstance(full_ticket, dict) else full_ticket
                    client_channel_id = ticket_data.get("channel_id")
                    logger.info(f"Fetched channel_id from full ticket: {client_channel_id}")
                except Exception as fetch_error:
                    logger.error(f"Failed to fetch full ticket data: {fetch_error}", exc_info=True)

            # Get claimed tickets category
            claimed_category = interaction.guild.get_channel(config.CLAIMED_TICKETS_CATEGORY_ID)
            logger.info(f"Claimed category: {claimed_category}")

            # Add exchanger to client channel and move to claimed category
            if client_channel_id:
                try:
                    client_channel = interaction.guild.get_channel(int(client_channel_id))
                    logger.info(f"Found client channel: {client_channel}")

                    if client_channel:
                        # Add exchanger permissions
                        logger.info(f"Adding {interaction.user.name} to client channel {client_channel.id}")
                        await client_channel.set_permissions(
                            interaction.user,
                            read_messages=True,
                            send_messages=True,
                            attach_files=True,
                            embed_links=True,
                            read_message_history=True
                        )
                        logger.info(f"✅ Added exchanger {interaction.user.name} to client channel {client_channel.id}")

                        # Move client channel to claimed category
                        if claimed_category:
                            logger.info(f"Moving client channel to claimed category {claimed_category.id}")
                            await client_channel.edit(category=claimed_category)
                            logger.info(f"✅ Moved client channel {client_channel.id} to claimed category")
                        else:
                            logger.error("Claimed category not found!")

                        # Post Transaction Panel in CLIENT channel
                        try:
                            logger.info("Importing TransactionPanelView")
                            from cogs.tickets.views.transaction_view import TransactionPanelView

                            logger.info("Creating transaction panel embed")

                            # Extract exchange details
                            send_method_id = ticket_data.get('send_method', 'Unknown')
                            receive_method_id = ticket_data.get('receive_method', 'Unknown')
                            send_crypto_id = ticket_data.get('send_crypto')
                            receive_crypto_id = ticket_data.get('receive_crypto')
                            amount_usd = ticket_data.get('amount_usd', 0)
                            fee_amount = ticket_data.get('fee_amount', 0)
                            fee_percentage = ticket_data.get('fee_percentage', 10)
                            receiving_amount = ticket_data.get('receiving_amount', 0)

                            # Calculate server fee (2% of amount or minimum $0.50)
                            server_fee = max(0.50, amount_usd * 0.02)

                            # Determine fee display (show "Min Fee" if it's the minimum fee)
                            MIN_FEE = 4.00
                            if fee_amount <= MIN_FEE:
                                fee_display = f"${fee_amount:.2f} (Min Fee)"
                            else:
                                fee_display = f"${fee_amount:.2f} ({fee_percentage}%)"

                            # Get payment method display names
                            from utils.payment_methods import format_payment_method_display

                            # Format send method (use crypto if specified, otherwise use payment method)
                            if send_crypto_id:
                                send_display_name = send_crypto_id.upper()
                            else:
                                send_display_name = format_payment_method_display(send_method_id)

                            # Format receive method (use crypto if specified, otherwise use payment method)
                            if receive_crypto_id:
                                receive_display_name = receive_crypto_id.upper()
                            else:
                                receive_display_name = format_payment_method_display(receive_method_id)

                            # Get custom Discord emojis (same logic as main exchange panel)
                            guild = interaction.guild if interaction else self.bot.get_guild(config.guild_id)

                            # Helper function to normalize emoji key
                            def normalize_emoji_key(key):
                                """Remove _balance, _card suffixes and convert to lowercase"""
                                if not key:
                                    return ""
                                key = key.lower()
                                # Remove common suffixes
                                for suffix in ["_balance", "_card", "_wallet"]:
                                    if key.endswith(suffix):
                                        key = key[:-len(suffix)]
                                return key

                            # Get emoji for send method
                            send_emoji_key = normalize_emoji_key(send_crypto_id or send_method_id)
                            send_emoji = "💵"  # default

                            if guild and hasattr(config, 'emoji_names'):
                                # Try exact match first
                                emoji_name = config.emoji_names.get(send_emoji_key)
                                if emoji_name:
                                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                                    if custom_emoji:
                                        send_emoji = str(custom_emoji)
                                        logger.debug(f"Found custom emoji for {send_emoji_key}: {emoji_name}")

                            # Get emoji for receive method
                            receive_emoji_key = normalize_emoji_key(receive_crypto_id or receive_method_id)
                            receive_emoji = "💰"  # default

                            if guild and hasattr(config, 'emoji_names'):
                                # Try exact match first
                                emoji_name = config.emoji_names.get(receive_emoji_key)
                                if emoji_name:
                                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                                    if custom_emoji:
                                        receive_emoji = str(custom_emoji)
                                        logger.debug(f"Found custom emoji for {receive_emoji_key}: {emoji_name}")

                            panel_embed = create_themed_embed(
                                title="",
                                description=(
                                    f"## 💱 Exchange In Progress\n\n"
                                    f"**Ticket:** #{ticket_data.get('ticket_number', 'Unknown')}\n"
                                    f"**Exchanger:** {interaction.user.mention}\n"
                                    f"**Status:** Claimed\n\n"
                                    f"### Exchange Details\n"
                                    f"**Sending:** {send_emoji} {send_display_name} ${amount_usd:.2f}\n"
                                    f"**Receiving:** {receive_emoji} {receive_display_name} ${receiving_amount:.2f}\n"
                                    f"**Amount:** ${amount_usd:.2f} USD\n"
                                    f"**Fee:** {fee_display}\n"
                                    f"**Client Receives:** ${receiving_amount:.2f} USD\n"
                                    f"**Server Fee:** ${server_fee:.2f}\n\n"
                                    f"### 📋 Next Steps\n\n"
                                    f"**For Customer:**\n"
                                    f"> 1. Send payment using the agreed method\n"
                                    f"> 2. Click **I Sent My Funds** below\n"
                                    f"> 3. Wait for exchanger to process payout\n\n"
                                    f"**For Exchanger:**\n"
                                    f"> 1. Verify customer's payment\n"
                                    f"> 2. Process payout to customer\n"
                                    f"> 3. Complete the ticket\n\n"
                                    f"### ⚙️ Actions\n"
                                    f"Use the buttons below to manage this exchange."
                                ),
                                color=PURPLE_GRADIENT
                            )

                            logger.info("Creating TransactionPanelView")
                            transaction_panel_view = TransactionPanelView(
                                bot=self.bot,
                                ticket_id=self.ticket_id,
                                channel=client_channel
                            )

                            logger.info(f"Sending Transaction Panel to client channel {client_channel.id}")
                            await client_channel.send(embed=panel_embed, view=transaction_panel_view)
                            logger.info(f"✅ Posted Transaction Panel in client channel {client_channel.id}")
                        except Exception as panel_error:
                            logger.error(f"❌ Error posting Transaction Panel: {panel_error}", exc_info=True)

                    else:
                        logger.error(f"Client channel {client_channel_id} not found in guild")
                except Exception as perm_error:
                    logger.error(f"❌ Error adding exchanger to client channel: {perm_error}", exc_info=True)
            else:
                logger.error(f"❌ No client_channel_id found in ticket data! Cannot move or add permissions.")

            # Update exchanger channel: lock from all roles except claimer
            # STAYS in Exchanger Tickets category (does NOT move)
            try:
                logger.info("Locking exchanger channel from all exchanger roles")
                send_method = ticket_data.get("send_method", "")
                receive_method = ticket_data.get("receive_method", "")
                payment_method_roles = self.get_payment_method_roles(send_method, receive_method)

                logger.info(f"Payment method roles to lock: {payment_method_roles}")

                # Lock ALL payment-specific exchanger roles
                for role_id in payment_method_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        await self.channel.set_permissions(
                            role,
                            read_messages=False  # Lock the channel from this role
                        )
                        logger.info(f"✅ Locked exchanger channel from {role.name}")
                    else:
                        logger.warning(f"Role {role_id} not found in guild")

                # Also lock the generic "All Exchangers" role if it's not already in the list
                ALL_EXCHANGERS_ROLE = 1381982080560402462
                if ALL_EXCHANGERS_ROLE not in payment_method_roles:
                    all_exch_role = interaction.guild.get_role(ALL_EXCHANGERS_ROLE)
                    if all_exch_role:
                        await self.channel.set_permissions(
                            all_exch_role,
                            read_messages=False
                        )
                        logger.info(f"✅ Locked exchanger channel from {all_exch_role.name} (All Exchangers)")

                # Add the claiming exchanger with full permissions
                await self.channel.set_permissions(
                    interaction.user,
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )
                logger.info(f"Gave {interaction.user.name} full permissions in exchanger channel")

                # IMPORTANT: Exchanger channel STAYS in Exchanger Tickets category
                # Do NOT move it to Claimed category
                logger.info(f"Exchanger channel {self.channel.id} remains in Exchanger Tickets category (locked)")

            except Exception as lock_error:
                logger.error(f"Error updating exchanger channel: {lock_error}")

            # Disable claim button
            for item in self.children:
                if item.custom_id == "claim_ticket_v2":
                    item.disabled = True
            await interaction.message.edit(view=self)

            # Success message
            embed = create_themed_embed(
                title="✅ Ticket Claimed!",
                description=f"You have successfully claimed this ticket!\n\n**Client Channel**: Moved to Claimed category, you have been added\n**Exchanger Channel**: Locked (only you can see it now)\n\nThe Exchange Panel has been posted in the client channel.",
                color=SUCCESS_GREEN
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Send message in exchanger channel
            claim_embed = create_themed_embed(
                title="",
                description=f"## ✅ Ticket Claimed\n\n{interaction.user.mention} has claimed this ticket!",
                color=SUCCESS_GREEN
            )
            await self.channel.send(embed=claim_embed)

        except Exception as e:
            logger.error(f"Error claiming ticket {self.ticket_id}: {e}", exc_info=True)
            error_message = str(e)
            error_title = "❌ Error"

            # Check for specific error types
            if "403" in error_message or "Forbidden" in error_message:
                # Admin permission denied
                error_title = "❌ Admin Permission Required"
                error_message = (
                    "You do not have permission to force-claim tickets.\n\n"
                    "**Only Head Admin or Assistant Admin** can claim tickets without having sufficient funds.\n\n"
                    "If you are a regular exchanger, please ensure you have sufficient funds deposited to claim this ticket."
                )
            elif "insufficient" in error_message.lower() or "balance" in error_message.lower():
                # Insufficient balance - try to extract required amount
                error_title = "❌ Insufficient Balance"
                if "need" in error_message.lower() or "required" in error_message.lower():
                    error_message = f"{error_message}\n\nPlease deposit the required amount and try again."
                else:
                    error_message = "You do not have sufficient funds to claim this ticket.\n\nPlease check your balance and deposit more funds, then try again."
            elif "already claimed" in error_message.lower():
                error_title = "❌ Already Claimed"
                error_message = "This ticket has already been claimed by another exchanger."
            elif "authentication failed" in error_message.lower():
                error_message = "Authentication failed. Please ensure you're logged in and try again."

            embed = create_themed_embed(
                title=error_title,
                description=f"{error_message}\n\nPlease contact support if this persists.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Client Info",
        style=discord.ButtonStyle.primary,
        emoji="ℹ️",
        custom_id="client_info"
    )
    async def client_info_button(self, button: Button, interaction: discord.Interaction):
        """Show anonymous client statistics"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get user context for authentication
            user_id = str(interaction.user.id)
            roles = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []

            # Get ticket data with authentication
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )

            ticket = result.get("ticket") if isinstance(result, dict) else result

            if not ticket:
                await interaction.followup.send("❌ Ticket not found.", ephemeral=True)
                return

            # Get client Discord ID
            client_discord_id = ticket.get("discord_user_id", ticket.get("user_id"))

            if not client_discord_id:
                await interaction.followup.send("❌ Client information not available.", ephemeral=True)
                return

            # Fetch client stats from backend
            try:
                stats_result = await self.bot.api_client.get(
                    f"/api/v1/users/{client_discord_id}/comprehensive-stats",
                    discord_user_id=user_id,
                    discord_roles=roles
                )
            except Exception as stats_err:
                logger.error(f"Error fetching client stats: {stats_err}")
                await interaction.followup.send("❌ Unable to fetch client statistics.", ephemeral=True)
                return

            # Calculate completion rate
            total_exchanges = stats_result.get("client_total_exchanges", 0)
            completed_exchanges = stats_result.get("client_completed_exchanges", 0)
            cancelled_exchanges = stats_result.get("client_cancelled_exchanges", 0)

            if total_exchanges > 0:
                completion_rate = (completed_exchanges / total_exchanges) * 100
            else:
                completion_rate = 0.0

            # Get Discord account age
            try:
                client_user = await self.bot.fetch_user(int(client_discord_id))
                account_created = client_user.created_at
                account_age_days = (datetime.utcnow() - account_created.replace(tzinfo=None)).days
            except:
                account_age_days = "Unknown"

            # Calculate risk level based on stats
            if total_exchanges == 0:
                risk_level = "MEDIUM"  # New user
            elif completion_rate >= 90 and total_exchanges >= 5:
                risk_level = "LOW"
            elif completion_rate >= 70:
                risk_level = "MEDIUM"
            elif cancelled_exchanges > completed_exchanges:
                risk_level = "HIGH"
            else:
                risk_level = "MEDIUM"

            # Risk level emoji
            risk_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴",
                "unknown": "⚪"
            }.get(risk_level.lower(), "⚪")

            description = (
                f"## 📊 Client Statistics\n\n"
                f"**Account Age:** {account_age_days} days\n"
                f"**Total Exchanges:** {total_exchanges}\n"
                f"**Completed:** {completed_exchanges}\n"
                f"**Cancelled:** {cancelled_exchanges}\n"
                f"**Completion Rate:** {completion_rate:.1f}%\n"
                f"{risk_emoji} **Risk Level:** {risk_level.upper()}\n\n"
                f"> *Client identity is kept anonymous for security.*"
            )

            embed = create_themed_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error fetching client info: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ Error fetching client information. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Ask Question",
        style=discord.ButtonStyle.secondary,
        emoji="❓",
        custom_id="ask_question"
    )
    async def ask_question_button(self, button: Button, interaction: discord.Interaction):
        """Ask a question (placeholder)"""
        await interaction.response.defer(ephemeral=True)

        embed = create_themed_embed(
            title="🚧 In Development",
            description=(
                "The **Ask Question** feature is currently in development.\n\n"
                "For now, please ping an admin if you have questions about this ticket."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    def has_exchanger_role(self, user) -> bool:
        """Check if user has any exchanger role (main or payment-specific)"""
        if not hasattr(user, 'roles'):
            return False

        # All exchanger role IDs
        EXCHANGER_ROLES = [
            1381982080560402462,  # All Exchangers
            1431732911140503583,  # PayPal Exchangers
            1431733031999377428,  # CashApp Exchangers
            1431733169777938594,  # ApplePay Exchangers
            1431733262367326370,  # Venmo Exchangers
            1431733429929775104,  # Zelle Exchangers
            1431733785086394408,  # Chime Exchangers
            1431734050217005136,  # Revolut Exchangers
            1431734179086860468,  # Skrill Exchangers
            1431734579290570752,  # Bank Exchangers
            1431734710744387684,  # PaySafe Exchangers
            1431734831028633650,  # Binance GiftCard Exchangers
        ]

        user_role_ids = {role.id for role in user.roles}
        has_role = any(role_id in user_role_ids for role_id in EXCHANGER_ROLES)

        if has_role:
            logger.info(f"User {user.name} has exchanger role")
        else:
            logger.warning(f"User {user.name} does NOT have any exchanger role. Their roles: {user_role_ids}")

        return has_role

    def get_payment_method_roles(self, send_method: str, receive_method: str) -> list:
        """Get exchanger role IDs based on payment methods"""
        # Payment method to role ID mapping
        PAYMENT_ROLES = {
            "PayPal": 1431732911140503583,
            "CashApp": 1431733031999377428,
            "ApplePay": 1431733169777938594,
            "Venmo": 1431733262367326370,
            "Zelle": 1431733429929775104,
            "Chime": 1431733785086394408,
            "Revolut": 1431734050217005136,
            "Skrill": 1431734179086860468,
            "Bank": 1431734579290570752,
            "PaySafe": 1431734710744387684,
            "Binance GiftCard": 1431734831028633650,
        }

        # All exchangers role
        ALL_EXCHANGERS = 1381982080560402462

        role_ids = []

        # Check if crypto to crypto (add all exchangers)
        is_send_crypto = any(crypto in send_method.upper() for crypto in ["BTC", "ETH", "LTC", "USDT", "SOL", "XRP", "CRYPTO"])
        is_receive_crypto = any(crypto in receive_method.upper() for crypto in ["BTC", "ETH", "LTC", "USDT", "SOL", "XRP", "CRYPTO"])

        if is_send_crypto and is_receive_crypto:
            # Crypto to crypto - add all exchangers
            role_ids.append(ALL_EXCHANGERS)
            logger.info("Crypto to crypto exchange - adding all exchangers")
        else:
            # Fiat or mixed - add specific payment method roles
            for method_name, role_id in PAYMENT_ROLES.items():
                if method_name.upper() in send_method.upper() or method_name.upper() in receive_method.upper():
                    role_ids.append(role_id)
                    logger.info(f"Adding {method_name} exchanger role")

        # Fallback to all exchangers if no specific roles found
        if not role_ids:
            role_ids.append(ALL_EXCHANGERS)
            logger.info("No specific roles found - adding all exchangers as fallback")

        return role_ids
