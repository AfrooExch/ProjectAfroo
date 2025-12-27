"""
Payout Views for V4
Handles internal (automatic from locked funds) and external (manual TXID) payouts
"""

import logging
from typing import Optional

import discord
from discord.ui import View, Button, Modal, InputText

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS, ERROR
from config import config

logger = logging.getLogger(__name__)


class PayoutMethodView(View):
    """View for selecting payout method (Internal vs External)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(timeout=None)  # Persistent - never times out
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="Internal Wallet",
        style=discord.ButtonStyle.primary,
        emoji="🏦",
        row=0
    )
    async def internal_button(self, button: Button, interaction: discord.Interaction):
        """Use internal wallet (locked funds)"""
        await interaction.response.defer(ephemeral=True)

        logger.info(f"Exchanger {interaction.user.id} selected internal payout for ticket #{self.ticket_id}")

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) and "ticket" in result else result

            # Verify it's the exchanger or admin with bypass
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            # Check for admin bypass (Head Admin or Assistant Admin)
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            # Debug logging
            logger.info(f"Internal payout: user={interaction.user.id}, exchanger={exchanger_discord_id}, admin_bypass={admin_bypass}, status={ticket.get('status')}, assigned_to={ticket.get('assigned_to')}")

            # Check permission (will fail naturally if exchanger_discord_id is None, unless admin bypass)
            if not admin_bypass and (not exchanger_discord_id or str(interaction.user.id) != str(exchanger_discord_id)):
                await interaction.followup.send(
                    "❌ Only the assigned exchanger can process payouts.",
                    ephemeral=True
                )
                return

            # Note: Buttons will be disabled after successful payout, not here
            # This allows users to re-select if they cancel the modal or encounter an error

            # Fetch exchanger's deposits with USD balances
            try:
                deposits_response = await self.bot.api_client.get(
                    f"/api/v1/exchanger/deposits/with-balances?ticket_id={self.ticket_id}",
                    discord_user_id=user_id,
                    discord_roles=roles
                )
                deposits = deposits_response.get("deposits", [])
            except Exception as e:
                logger.error(f"Error fetching deposits: {e}")
                await interaction.followup.send(
                    f"❌ Error fetching your deposits: {str(e)}",
                    ephemeral=True
                )
                return

            if not deposits:
                await interaction.followup.send(
                    "❌ You don't have sufficient funds in any cryptocurrency to cover this payout.\n"
                    f"**Required:** ${ticket.get('receiving_amount', 0):.2f} USD",
                    ephemeral=True
                )
                return

            # Show coin selector
            coin_view = CoinSelectionView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel,
                ticket_data=ticket,
                deposits=deposits
            )

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 💰 Select Cryptocurrency\n\n"
                    f"Choose which cryptocurrency to send to the customer.\n\n"
                    f"**Required Amount:** ${ticket.get('receiving_amount', 0):.2f} USD\n\n"
                    f"Only coins with sufficient balance are shown below."
                ),
                color=PURPLE_GRADIENT
            )

            await self.channel.send(
                f"<@{exchanger_discord_id}>",
                embed=embed,
                view=coin_view
            )

            await interaction.followup.send(
                "✅ Please select a cryptocurrency from the dropdown below.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error processing internal payout: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="External Wallet",
        style=discord.ButtonStyle.secondary,
        emoji="🔗",
        row=0
    )
    async def external_button(self, button: Button, interaction: discord.Interaction):
        """Use external wallet (manual TXID)"""
        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) and "ticket" in result else result

            # Verify it's the exchanger or admin with bypass
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            # Check for admin bypass (Head Admin or Assistant Admin)
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            # Debug logging
            logger.info(f"External payout: user={interaction.user.id}, exchanger={exchanger_discord_id}, admin_bypass={admin_bypass}, status={ticket.get('status')}, assigned_to={ticket.get('assigned_to')}")

            # Check permission (will fail naturally if exchanger_discord_id is None, unless admin bypass)
            if not admin_bypass and (not exchanger_discord_id or str(interaction.user.id) != str(exchanger_discord_id)):
                await interaction.response.send_message(
                    "❌ Only the assigned exchanger can process payouts.",
                    ephemeral=True
                )
                return

            # Show TXID input modal FIRST (must respond within 3 seconds)
            modal = ExternalPayoutModal(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel,
                ticket_data=ticket,
                payout_view=self  # Pass view reference to disable buttons on success
            )
            await interaction.response.send_modal(modal)

            # Note: Buttons will be disabled by the modal callback after successful payout
            # This allows users to retry if they cancel the modal or encounter an error

            logger.info(f"Exchanger {interaction.user.id} selected external payout for ticket #{self.ticket_id}")

        except Exception as e:
            logger.error(f"Error processing external payout: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


class CoinSelectionView(View):
    """View for selecting which cryptocurrency to use for internal payout"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict, deposits: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data
        self.deposits = deposits

        # Add select dropdown with available coins
        self.add_coin_select()

    def add_coin_select(self):
        """Add dropdown with available cryptocurrencies"""
        options = []

        for deposit in self.deposits:
            currency = deposit.get("currency", "???")
            balance_crypto = deposit.get("balance", "0")
            balance_usd = deposit.get("balance_usd", 0)

            # Create option
            options.append(discord.SelectOption(
                label=f"{currency} - ${balance_usd:.2f} USD",
                description=f"Balance: {balance_crypto} {currency}",
                value=currency,
                emoji="💰"
            ))

        # Create select menu
        select = discord.ui.Select(
            placeholder="Choose cryptocurrency to send",
            options=options,
            custom_id="coin_select",
            row=0
        )
        select.callback = self.coin_selected
        self.add_item(select)

    async def coin_selected(self, interaction: discord.Interaction):
        """Handle coin selection"""
        selected_currency = interaction.data["values"][0]

        logger.info(f"Exchanger {interaction.user.id} selected {selected_currency} for payout on ticket #{self.ticket_id}")

        # Show wallet address input modal
        modal = InternalPayoutModal(
            bot=self.bot,
            ticket_id=self.ticket_id,
            channel=self.channel,
            ticket_data=self.ticket_data,
            selected_currency=selected_currency
        )

        await interaction.response.send_modal(modal)

        # Disable the select after selection
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)


class ShowInternalModalView(View):
    """Temporary view to show internal payout modal"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data

    @discord.ui.button(
        label="Enter Wallet Address",
        style=discord.ButtonStyle.primary,
        emoji="💳"
    )
    async def enter_address_button(self, button: Button, interaction: discord.Interaction):
        """Show wallet address modal"""
        modal = InternalPayoutModal(
            bot=self.bot,
            ticket_id=self.ticket_id,
            channel=self.channel,
            ticket_data=self.ticket_data
        )
        await interaction.response.send_modal(modal)


class InternalPayoutModal(Modal):
    """Modal for internal payout (using locked funds)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict, selected_currency: str = None):
        super().__init__(title="Internal Payout")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data
        self.selected_currency = selected_currency or ticket_data.get("receive_crypto", "crypto")

        self.wallet_address_input = InputText(
            label=f"Customer's {self.selected_currency.upper()} Wallet Address",
            placeholder="Enter the wallet address to send funds to...",
            required=True,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.wallet_address_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle internal payout"""
        await interaction.response.defer(ephemeral=True)

        wallet_address = self.wallet_address_input.value.strip()

        logger.info(f"Processing internal payout for ticket #{self.ticket_id} to address {wallet_address[:10]}... using {self.selected_currency}")

        try:
            # Process internal payout via API
            # This will:
            # 1. Use locked funds from hold
            # 2. Send crypto via blockchain
            # 3. Release hold
            # 4. Return transaction hash
            result = await self.bot.api_client.process_internal_payout(
                ticket_id=self.ticket_id,
                wallet_address=wallet_address,
                currency=self.selected_currency
            )

            tx_hash = result.get("tx_hash", "")
            amount = result.get("amount", 0)
            asset = result.get("asset", self.selected_currency)

            # Post payout success
            embed = create_success_embed(
                title="Payout Sent (Internal)",
                description=(
                    f"**Amount:** `{amount} {asset.upper()}`\n"
                    f"**To Address:** `{wallet_address[:20]}...`\n"
                    f"**Transaction Hash:** `{tx_hash[:20]}...`\n\n"
                    f"Funds have been sent from your locked deposits.\n\n"
                    f"Waiting for customer confirmation..."
                )
            )

            await self.channel.send(embed=embed)

            # Show confirmation buttons to customer
            await self.post_customer_confirmation()

            await interaction.followup.send(
                "✅ Internal payout processed successfully!",
                ephemeral=True
            )

            logger.info(f"Internal payout completed for ticket #{self.ticket_id}: {tx_hash}")

        except APIError as e:
            logger.error(f"API error processing internal payout: {e}")
            await interaction.followup.send(
                f"❌ Payout failed: {e.user_message}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error processing internal payout: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error processing payout: {str(e)}",
                ephemeral=True
            )

    async def post_customer_confirmation(self):
        """Post customer confirmation buttons"""
        # Use correct field name from V4 API
        customer_discord_id = self.ticket_data.get("discord_user_id")
        customer_id = int(customer_discord_id) if customer_discord_id else 0

        if not customer_id:
            logger.error(f"No customer_id found in ticket data for ticket {self.ticket_id}")
            customer_id = 0  # Fallback to avoid crash

        embed = create_themed_embed(
            title="",
            description=(
                f"## Confirm Receipt\n\n"
                f"<@{customer_id}> The exchanger has sent your payout.\n\n"
                f"**Please confirm:**\n"
                f"> Did you receive the payment?\n\n"
                f"Click **I Received Payment** once you've confirmed the transaction."
            ),
            color=PURPLE_GRADIENT
        )

        view = CustomerConfirmationView(
            bot=self.bot,
            ticket_id=self.ticket_id,
            channel=self.channel
        )

        await self.channel.send(content=f"<@{customer_id}>", embed=embed, view=view)


class ExternalPayoutModal(Modal):
    """Modal for external payout (manual TXID verification)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict, payout_view=None):
        super().__init__(title="External Payout")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data
        self.payout_view = payout_view  # Reference to parent view to disable buttons on success

        self.txid_input = InputText(
            label="Transaction Hash (TXID)",
            placeholder="Paste the transaction hash from your wallet...",
            required=True,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.txid_input)

        self.wallet_address_input = InputText(
            label="Customer's Wallet Address (sent to)",
            placeholder="Wallet address you sent funds to...",
            required=True,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.wallet_address_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle external payout"""
        await interaction.response.defer(ephemeral=True)

        tx_hash = self.txid_input.value.strip()
        wallet_address = self.wallet_address_input.value.strip()

        logger.info(f"Processing external payout for ticket #{self.ticket_id} - TXID: {tx_hash[:10]}...")

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Verify and process external payout via API
            # This will:
            # 1. Verify transaction on blockchain
            # 2. Check amount and recipient
            # 3. Keep hold (funds not used)
            # 4. Update ticket status
            result = await self.bot.api_client.process_external_payout(
                ticket_id=self.ticket_id,
                tx_hash=tx_hash,
                wallet_address=wallet_address,
                discord_user_id=user_id,
                discord_roles=roles
            )

            verified = result.get("verified", False)
            amount = result.get("amount", 0)
            asset = result.get("asset", "crypto")

            # Check if this is a crypto payment (has blockchain network)
            payment_method = self.ticket_data.get("payment_method", "crypto")
            is_crypto = payment_method == "crypto" or asset.upper() in ["BTC", "ETH", "SOL", "LTC", "USDT", "USDC", "XRP", "BNB", "TRX"]

            # Build description based on payment type
            description_parts = [f"## Payout Sent\n"]
            description_parts.append(f"**Amount:** `{amount} {asset.upper()}`\n")

            if is_crypto:
                # Show blockchain-specific fields for crypto
                description_parts.append(f"**To Address:** `{wallet_address[:20]}...`\n")
                description_parts.append(f"**Transaction Hash:** `{tx_hash[:20]}...`\n")
                description_parts.append(f"**Verification:** {'✅ Auto-verified' if verified else '⏳ Manual review needed'}\n")
            else:
                # For fiat, show transaction reference instead
                description_parts.append(f"**Transaction Reference:** `{tx_hash[:30]}...`\n")
                description_parts.append(f"**Verification:** ⏳ Manual review needed\n")

            description_parts.append(f"\n> Funds sent from your external wallet/account\n")
            description_parts.append(f"> Your locked deposit remains intact\n\n")
            description_parts.append(f"Waiting for customer confirmation...")

            # Use purple gradient for consistency
            embed = create_themed_embed(
                title="",
                description="".join(description_parts),
                color=PURPLE_GRADIENT
            )

            await self.channel.send(embed=embed)

            # Show confirmation buttons to customer
            await self.post_customer_confirmation()

            # Disable payout buttons now that payout is successful
            if self.payout_view:
                try:
                    for item in self.payout_view.children:
                        item.disabled = True
                    # Get the original message and update it
                    async for message in self.channel.history(limit=50):
                        if message.components and any(hasattr(c, 'children') for c in message.components):
                            for component in message.components:
                                if hasattr(component, 'children'):
                                    for child in component.children:
                                        if hasattr(child, 'label') and ('Internal Wallet' in str(child.label) or 'External Wallet' in str(child.label)):
                                            await message.edit(view=self.payout_view)
                                            break
                except Exception as e:
                    logger.warning(f"Could not disable payout buttons: {e}")

            await interaction.followup.send(
                "✅ External payout submitted successfully!",
                ephemeral=True
            )

            logger.info(f"External payout submitted for ticket #{self.ticket_id}: {tx_hash}")

        except APIError as e:
            logger.error(f"API error processing external payout: {e}")
            await interaction.followup.send(
                f"❌ Payout verification failed: {e.user_message}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error processing external payout: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error processing payout: {str(e)}",
                ephemeral=True
            )

    async def post_customer_confirmation(self):
        """Post customer confirmation buttons"""
        # Use correct field name from V4 API
        customer_discord_id = self.ticket_data.get("discord_user_id")
        customer_id = int(customer_discord_id) if customer_discord_id else 0

        if not customer_id:
            logger.error(f"No customer_id found in ticket data for ticket {self.ticket_id}")
            customer_id = 0  # Fallback to avoid crash

        embed = create_themed_embed(
            title="",
            description=(
                f"## Confirm Receipt\n\n"
                f"<@{customer_id}> The exchanger has sent your payout.\n\n"
                f"**Please confirm:**\n"
                f"> Did you receive the payment?\n\n"
                f"Click **I Received Payment** once you've confirmed the transaction."
            ),
            color=PURPLE_GRADIENT
        )

        view = CustomerConfirmationView(
            bot=self.bot,
            ticket_id=self.ticket_id,
            channel=self.channel
        )

        await self.channel.send(content=f"<@{customer_id}>", embed=embed, view=view)


class CustomerConfirmationView(View):
    """View for customer to confirm receiving payment"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(timeout=None)  # Persistent - never times out
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="I Received Payment",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(self, button: Button, interaction: discord.Interaction):
        """Customer confirms receiving payment"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket
            ticket = await self.bot.api_client.get_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Verify it's the customer - use correct field name
            customer_discord_id = ticket.get("discord_user_id")
            customer_id = int(customer_discord_id) if customer_discord_id else 0

            if not customer_id or interaction.user.id != customer_id:
                await interaction.followup.send(
                    "❌ Only the customer can confirm payment receipt.",
                    ephemeral=True
                )
                return

            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Complete the ticket
            from cogs.tickets.handlers.completion_handler import complete_ticket

            await complete_ticket(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel,
                ticket_data=ticket
            )

            await interaction.followup.send(
                "✅ Thank you for confirming! The ticket will be completed shortly.",
                ephemeral=True
            )

            logger.info(f"Customer confirmed payment receipt for ticket #{self.ticket_id}")

        except Exception as e:
            logger.error(f"Error confirming payment: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="I Have an Issue",
        style=discord.ButtonStyle.danger,
        emoji="⚠️"
    )
    async def issue_button(self, button: Button, interaction: discord.Interaction):
        """Customer reports an issue"""
        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket
            ticket = await self.bot.api_client.get_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Verify it's the customer - use correct field name
            customer_discord_id = ticket.get("discord_user_id")
            customer_id = int(customer_discord_id) if customer_discord_id else 0

            if not customer_id or interaction.user.id != customer_id:
                await interaction.response.send_message(
                    "❌ Only the customer can report issues.",
                    ephemeral=True
                )
                return

            # Show issue modal
            modal = PaymentIssueModal(self.bot, self.ticket_id, self.channel)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error reporting issue: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


class PaymentIssueModal(Modal):
    """Modal for reporting payment issues"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Report Issue")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.issue_input = InputText(
            label="Describe the issue",
            placeholder="Explain what went wrong with the payment...",
            required=True,
            max_length=1000,
            style=discord.InputTextStyle.paragraph
        )
        self.add_item(self.issue_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle issue report"""
        await interaction.response.defer(ephemeral=True)

        issue_description = self.issue_input.value.strip()

        logger.warning(f"Payment issue reported for ticket #{self.ticket_id}: {issue_description}")

        # Get user context for API authentication
        from utils.auth import get_user_context
        user_id, roles = get_user_context(interaction)

        # Post issue alert
        embed = create_error_embed(
            title="⚠️ Payment Issue Reported",
            description=(
                f"**Reported by:** {interaction.user.mention}\n\n"
                f"**Issue:**\n{issue_description}\n\n"
                f"**Staff:** Please investigate this ticket."
            )
        )

        # Get admin role
        admin_role_id = config.HEAD_ADMIN_ROLE_ID
        admin_role = self.channel.guild.get_role(admin_role_id)
        mention = admin_role.mention if admin_role else "@Admin"

        await self.channel.send(content=mention, embed=embed)

        # Update ticket status
        try:
            await self.bot.api_client.update_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles,
                status="disputed",
                dispute_reason=issue_description
            )
        except:
            pass

        await interaction.followup.send(
            "✅ Issue reported. Staff has been notified.",
            ephemeral=True
        )
