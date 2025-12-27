"""AutoMM Buyer Protection Escrow Handler - Secure escrow for purchasing services/items"""
import logging
import discord
import asyncio
import io
import qrcode
from discord.ui import View, Button, Modal, InputText
from utils.embeds import create_themed_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED
from config import config

logger = logging.getLogger(__name__)


async def create_buyer_escrow(interaction, buyer, seller, usd_amount, crypto, service_description, bot):
    """
    Create buyer-protection escrow transaction.

    Flow:
    1. Create private escrow channel
    2. Generate escrow wallet via API
    3. Buyer deposits funds
    4. Bot monitors blockchain
    5. Seller provides service
    6. Buyer releases funds
    7. Bot sends to seller's wallet
    """
    guild = interaction.guild

    try:
        # Create private escrow channel
        channel = await create_escrow_channel(guild, buyer, seller)

        # Success message to buyer
        await interaction.followup.send(
            embed=create_success_embed(
                title="Escrow Created",
                description=f"✅ Escrow transaction created!\n\n{channel.mention}\n\nDeposit instructions posted in the channel."
            ),
            ephemeral=True
        )

        # Generate escrow wallet via API
        api = bot.api_client
        result = await api.post(
            "/api/v1/automm/create-buyer-escrow",
            data={
                "buyer_id": str(buyer.id),
                "seller_id": str(seller.id),
                "amount": usd_amount,
                "crypto": crypto,
                "service_description": service_description,
                "channel_id": str(channel.id)
            },
            discord_user_id=str(buyer.id),
            discord_roles=[role.id for role in buyer.roles]
        )

        escrow_id = result.get("escrow_id")
        deposit_address = result.get("deposit_address")

        # Post escrow details in channel
        await post_escrow_details(
            channel=channel,
            buyer=buyer,
            seller=seller,
            usd_amount=usd_amount,
            crypto=crypto,
            service_description=service_description,
            deposit_address=deposit_address,
            escrow_id=escrow_id,
            bot=bot
        )

        logger.info(f"Created buyer escrow {escrow_id}: {buyer.name} -> {seller.name} | ${usd_amount} USD ({crypto})")

    except Exception as e:
        logger.error(f"Error creating buyer escrow: {e}", exc_info=True)
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


async def create_escrow_channel(guild, buyer, seller):
    """Create private escrow channel"""
    category = guild.get_channel(config.CATEGORY_ESCROW)
    admin_role = guild.get_role(config.ROLE_ADMIN)
    staff_role = guild.get_role(config.ROLE_STAFF)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        buyer: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True, attach_files=True),
        seller: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True, manage_messages=True)
    }

    if admin_role:
        overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True, manage_messages=True)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True)

    channel = await category.create_text_channel(
        name=f"escrow-{buyer.name[:10]}-{seller.name[:10]}",
        overwrites=overwrites,
        topic=f"Escrow: {buyer.name} (Buyer) ↔ {seller.name} (Seller)"
    )
    return channel


async def post_escrow_details(channel, buyer, seller, usd_amount, crypto, service_description, deposit_address, escrow_id, bot):
    """Post escrow details and instructions"""
    # Get short MM ID (last 8 characters of escrow_id)
    mm_id = escrow_id[-8:].upper()

    embed = create_themed_embed(
        title="",
        description=(
            f"## 🔒 Escrow Transaction Created\n\n"
            f"**MM ID:** `{mm_id}`\n"
            f"**Escrow ID:** `{escrow_id}`\n\n"
            f"### Parties\n\n"
            f"**Buyer:** {buyer.mention}\n"
            f"**Seller:** {seller.mention}\n\n"
            f"### Transaction Details\n\n"
            f"**Amount:** `${usd_amount:.2f} USD` in **{crypto}**\n"
            f"**Service:** {service_description}\n\n"
            f"## How This Works\n\n"
            f"> 1. **Buyer deposits** crypto worth `${usd_amount:.2f} USD` to escrow wallet\n"
            f"> 2. **Bot confirms** blockchain deposit\n"
            f"> 3. **Seller provides** service/item\n"
            f"> 4. **Buyer releases** funds after satisfied\n"
            f"> 5. **Bot sends** funds to seller's wallet ✅\n\n"
            f"## Step 1: Buyer Deposit\n\n"
            f"**{buyer.mention}**, send `${usd_amount:.2f} USD` worth of **{crypto}** to:\n\n"
            f"```\n{deposit_address}\n```\n\n"
            f"> ⚠️ Send from your personal wallet (NOT an exchange)\n"
            f"> ⚠️ Use current market rates to calculate crypto amount\n\n"
            f"After depositing, click **\"Check Deposit\"** below to verify."
        ),
        color=PURPLE_GRADIENT
    )

    view = EscrowControlsView(bot, escrow_id, mm_id, buyer.id, seller.id, usd_amount, crypto, deposit_address)
    await channel.send(
        content=f"{buyer.mention} {seller.mention}",
        embed=embed,
        view=view
    )


class EscrowControlsView(View):
    """Controls for escrow participants"""
    def __init__(self, bot, escrow_id, mm_id, buyer_id, seller_id, usd_amount, crypto, deposit_address):
        super().__init__(timeout=None)
        self.bot = bot
        self.escrow_id = escrow_id
        self.mm_id = mm_id
        self.buyer_id = buyer_id
        self.seller_id = seller_id
        self.usd_amount = usd_amount
        self.crypto = crypto
        self.deposit_address = deposit_address

    @discord.ui.button(label="Copy Address", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def copy_address_button(self, button, interaction):
        """Copy deposit address for mobile users"""
        await interaction.response.send_message(
            f"**Deposit Address:**\n```\n{self.deposit_address}\n```\nTap and hold to copy!",
            ephemeral=True
        )

    @discord.ui.button(label="QR Code", style=discord.ButtonStyle.secondary, emoji="📱", row=0)
    async def qr_code_button(self, button, interaction):
        """Generate QR code for deposit address"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(self.deposit_address)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            file = discord.File(buffer, filename=f"escrow_qr_{self.escrow_id[-8:]}.png")

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 📱 Scan QR Code\n\n"
                    f"**Deposit Address:**\n"
                    f"```\n{self.deposit_address}\n```\n\n"
                    f"**Amount:** `${self.usd_amount:.2f} USD` in **{self.crypto}**\n\n"
                    f"> Scan with your crypto wallet app"
                ),
                color=PURPLE_GRADIENT
            )
            embed.set_image(url=f"attachment://escrow_qr_{self.escrow_id[-8:]}.png")

            await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        except Exception as e:
            logger.error(f"Error generating QR code: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error generating QR code: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Check Deposit", style=discord.ButtonStyle.primary, emoji="🔍", row=0)
    async def check_deposit_button(self, button, interaction):
        """Check if buyer deposited funds"""
        await interaction.response.defer()

        try:
            # Check blockchain via API
            api = self.bot.api_client
            result = await api.get(
                f"/api/v1/automm/{self.escrow_id}/check-deposit",
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            status = result.get("status", "not_received")
            balance = result.get("balance", 0)

            # Show status
            if status == "confirmed":
                # Get TX hash from Tatum (check recent transactions)
                tx_info = ""
                try:
                    # Get recent transactions to find the deposit TX
                    from app.services.tatum_service import TatumService
                    tx_url = TatumService.get_explorer_url(self.crypto, "view address")
                    tx_info = f"\n**Explorer:** [View on blockchain]({tx_url.replace('view address', self.deposit_address)})"
                except:
                    pass

                # Send NEW embed with full transaction details
                embed = create_themed_embed(
                    title="",
                    description=(
                        f"## ✅ Deposit Confirmed\n\n"
                        f"**Status:** Confirmed on blockchain\n"
                        f"**Amount Received:** `{balance} {self.crypto}`\n"
                        f"**USD Value:** `${self.usd_amount:.2f} USD`\n"
                        f"**Confirmations:** Sufficient ✅{tx_info}\n\n"
                        f"## Step 2: Service Delivery\n\n"
                        f"**<@{self.seller_id}>** (Seller): You can now provide the service/item.\n\n"
                        f"**<@{self.buyer_id}>** (Buyer): Once you receive and are satisfied with the service, click **\"Release Funds\"** below.\n\n"
                        f"> ⚠️ Only release funds after you've received what you paid for!"
                    ),
                    color=PURPLE_GRADIENT
                )

                # Disable check buttons, enable release button
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label in ["Check Deposit", "Force Check", "Copy Address"]:
                            item.disabled = True
                        elif item.label == "Release Funds":
                            item.disabled = False

                await interaction.message.edit(view=self)
                await interaction.channel.send(embed=embed)

            elif status == "pending_confirmation":
                await interaction.followup.send(
                    f"⏳ **Pending Confirmations**\n\n"
                    f"Detected: `{balance} {self.crypto}`\n"
                    f"Waiting for blockchain confirmations...",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **No Deposit Detected**\n\n"
                    f"No funds have been received yet.\n"
                    f"Please send to:\n```\n{self.deposit_address}\n```",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error checking deposit: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Force Check", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def force_check_button(self, button, interaction):
        """Force blockchain check if auto-check fails"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Same as check deposit but ephemeral response
            api = self.bot.api_client
            result = await api.get(
                f"/api/v1/automm/{self.escrow_id}/check-deposit",
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            status = result.get("status", "not_received")
            balance = result.get("balance", 0)

            if status == "confirmed":
                await interaction.followup.send(f"✅ Deposit confirmed: `{balance} {self.crypto}`", ephemeral=True)
            elif status == "pending_confirmation":
                await interaction.followup.send(f"⏳ Pending: `{balance} {self.crypto}` (waiting for confirmations)", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ No deposit detected yet", ephemeral=True)

        except Exception as e:
            logger.error(f"Error forcing blockchain check: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Release Funds", style=discord.ButtonStyle.success, emoji="✅", disabled=True, row=1)
    async def release_funds_button(self, button, interaction):
        """Buyer confirms satisfaction and releases funds"""
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("❌ Only the buyer can release funds.", ephemeral=True)
            return

        await interaction.response.defer()

        # Check blockchain confirmations FIRST before releasing
        try:
            api = self.bot.api_client
            result = await api.get(
                f"/api/v1/automm/{self.escrow_id}/check-deposit",
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            status = result.get("status", "not_received")
            confirmations = result.get("confirmations", 0)

            # Check if we have sufficient confirmations (3+ for most cryptos)
            min_confirmations = 3

            if status != "confirmed" or confirmations < min_confirmations:
                await interaction.followup.send(
                    f"⏳ **Insufficient Confirmations**\n\n"
                    f"The deposit has **{confirmations}/{min_confirmations}** confirmations.\n"
                    f"Please wait for **{min_confirmations}** blockchain confirmations before releasing funds.\n\n"
                    f"This usually takes a few minutes. You can try clicking **\"Release Funds\"** again once more confirmations are received.",
                    ephemeral=True
                )
                return

        except Exception as e:
            logger.error(f"Error checking confirmations before release: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error checking blockchain confirmations. Please try again in a moment.",
                ephemeral=True
            )
            return

        # Sufficient confirmations - proceed with release
        # Disable release button
        button.disabled = True
        await interaction.message.edit(view=self)

        # Send embed asking seller to enter their wallet address
        embed = create_themed_embed(
            title="",
            description=(
                f"## ✅ Buyer Approved Release\n\n"
                f"**<@{self.buyer_id}>** has confirmed satisfaction with the service.\n\n"
                f"## Step 3: Seller Withdrawal\n\n"
                f"**<@{self.seller_id}>** (Seller): Click the button below to enter your **{self.crypto}** wallet address to receive your payment.\n\n"
                f"**Amount to receive:** `{self.usd_amount:.2f} USD` in **{self.crypto}**\n\n"
                f"> ⚠️ Make sure you enter the correct address for **{self.crypto}**!\n"
                f"> ⚠️ Double-check the address before submitting - transactions cannot be reversed!"
            ),
            color=PURPLE_GRADIENT
        )

        view = SellerAddressView(self.bot, self.escrow_id, self.seller_id, self.buyer_id, self.usd_amount, self.crypto)
        await interaction.channel.send(embed=embed, view=view)

    @discord.ui.button(label="Dispute", style=discord.ButtonStyle.danger, emoji="⚠️", row=1)
    async def dispute_button(self, button, interaction):
        """Raise a dispute - pings admin"""
        if interaction.user.id not in [self.buyer_id, self.seller_id]:
            await interaction.response.send_message("❌ Only participants can raise disputes.", ephemeral=True)
            return

        # Get admin role
        admin_role = interaction.guild.get_role(config.ROLE_ADMIN)
        admin_ping = admin_role.mention if admin_role else "@Admin"

        await interaction.response.send_message(
            f"⚠️ **DISPUTE RAISED**\n\n"
            f"{admin_ping} - Escrow **MM #{self.mm_id}** needs staff intervention\n\n"
            f"**Raised by:** {interaction.user.mention}\n"
            f"**Escrow ID:** `{self.escrow_id}`",
            ephemeral=False
        )

    @discord.ui.button(label="Request Cancel", style=discord.ButtonStyle.secondary, emoji="🔙", row=1)
    async def cancel_button(self, button, interaction):
        """Request to cancel and refund escrow - requires both parties approval"""
        if interaction.user.id not in [self.buyer_id, self.seller_id]:
            await interaction.response.send_message("❌ Only participants can request cancellation.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Get current escrow state
            api = self.bot.api_client
            escrow_result = await api.get(
                f"/api/v1/automm/{self.escrow_id}",
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )
            escrow = escrow_result.get("escrow", {})

            # Check if already cancelled or completed
            if escrow.get("status") in ["cancelled", "completed"]:
                await interaction.followup.send(f"❌ Escrow is already {escrow['status']}.", ephemeral=True)
                return

            # Check if already requested
            cancel_requested_by = escrow.get("cancel_requested_by")
            cancel_approved_by = escrow.get("cancel_approved_by", [])

            # Convert user ID to string for comparison
            user_id_str = str(interaction.user.id)

            if user_id_str in cancel_approved_by:
                await interaction.followup.send("✅ You've already approved the cancellation.", ephemeral=True)
                return

            # Add user to cancel approval list
            await api.post(
                f"/api/v1/automm/{self.escrow_id}/request-cancel",
                data={"user_id": user_id_str},
                discord_user_id=user_id_str,
                discord_roles=[role.id for role in interaction.user.roles]
            )

            # Get updated escrow state
            escrow_result = await api.get(
                f"/api/v1/automm/{self.escrow_id}",
                discord_user_id=user_id_str,
                discord_roles=[role.id for role in interaction.user.roles]
            )
            escrow = escrow_result.get("escrow", {})
            cancel_approved_by = escrow.get("cancel_approved_by", [])

            # Check if both parties approved (compare strings to strings)
            buyer_approved = str(self.buyer_id) in cancel_approved_by
            seller_approved = str(self.seller_id) in cancel_approved_by

            if buyer_approved and seller_approved:
                # Both approved - check if deposit was made
                deposit_status = escrow.get("deposit_status", "not_received")
                balance = float(escrow.get("balance", 0))

                if deposit_status == "not_received" or balance == 0:
                    # No deposit made - just close the escrow
                    embed = create_themed_embed(
                        title="",
                        description=(
                            f"## Cancellation Approved\n\n"
                            f"Both parties agreed to cancel this escrow.\n\n"
                            f"No funds were deposited, so no refund is needed.\n\n"
                            f"This channel will close in 60 seconds."
                        ),
                        color=PURPLE_GRADIENT
                    )
                    await interaction.channel.send(embed=embed)

                    # Generate and post transcript
                    try:
                        buyer_member = interaction.guild.get_member(int(self.buyer_id))
                        seller_member = interaction.guild.get_member(int(self.seller_id))
                        transcript_html = await generate_transcript(self.bot, interaction.channel, self.escrow_id, buyer_member, seller_member)

                        if transcript_html:
                            transcript_url = await upload_transcript_to_url(self.escrow_id, transcript_html)
                            await post_transcript_to_channel(
                                bot=self.bot,
                                guild=interaction.guild,
                                escrow_id=self.escrow_id,
                                buyer_id=self.buyer_id,
                                seller_id=self.seller_id,
                                transcript_html=transcript_html
                            )
                    except Exception as e:
                        logger.error(f"Error generating transcript: {e}", exc_info=True)

                    # Close channel after delay
                    await asyncio.sleep(60)
                    await interaction.channel.delete(reason="Escrow cancelled - no funds deposited")
                else:
                    # Deposit was made - process refund
                    embed = create_themed_embed(
                        title="",
                        description=(
                            f"## Cancellation Approved\n\n"
                            f"Both parties agreed to cancel this escrow.\n\n"
                            f"Processing refund to buyer..."
                        ),
                        color=PURPLE_GRADIENT
                    )
                    await interaction.channel.send(embed=embed)

                    # Request refund
                    view = BuyerRefundAddressView(self.bot, self.escrow_id, self.buyer_id, self.seller_id, self.usd_amount, self.crypto)
                    refund_embed = create_themed_embed(
                        title="",
                        description=(
                            f"## Refund Process\n\n"
                            f"**<@{self.buyer_id}>** (Buyer): Click the button below to enter your **{self.crypto}** wallet address for the refund.\n\n"
                            f"**Amount to refund:** `${self.usd_amount:.2f} USD` in **{self.crypto}**\n\n"
                            f"Make sure you enter the correct address."
                        ),
                        color=PURPLE_GRADIENT
                    )
                    await interaction.channel.send(embed=refund_embed, view=view)

            else:
                # One party approved, waiting for other
                other_party = "Seller" if interaction.user.id == self.buyer_id else "Buyer"
                other_id = self.seller_id if interaction.user.id == self.buyer_id else self.buyer_id

                embed = create_themed_embed(
                    title="",
                    description=(
                        f"## Cancellation Requested\n\n"
                        f"**{interaction.user.mention}** has requested to cancel this escrow.\n\n"
                        f"**<@{other_id}>** ({other_party}): Click the \"Request Cancel\" button above to approve the cancellation.\n\n"
                        f"**Approval Status:**\n"
                        f"Buyer: {'Approved' if buyer_approved else 'Pending'}\n"
                        f"Seller: {'Approved' if seller_approved else 'Pending'}\n\n"
                        f"Both parties must agree to cancel."
                    ),
                    color=PURPLE_GRADIENT
                )
                await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error requesting cancellation: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


class SellerAddressView(View):
    """View for seller to enter their wallet address"""
    def __init__(self, bot, escrow_id, seller_id, buyer_id, amount, crypto):
        super().__init__(timeout=None)
        self.bot = bot
        self.escrow_id = escrow_id
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.amount = amount
        self.crypto = crypto

    @discord.ui.button(label=f"Enter My Wallet Address", style=discord.ButtonStyle.success, emoji="💳")
    async def enter_address_button(self, button, interaction):
        """Seller clicks to open modal"""
        if interaction.user.id != self.seller_id:
            await interaction.response.send_message("❌ Only the seller can enter their wallet address.", ephemeral=True)
            return

        # Show modal to seller
        modal = SellerAddressModal(self.bot, self.escrow_id, self.seller_id, self.buyer_id, self.amount, self.crypto)
        await interaction.response.send_modal(modal)


class SellerAddressModal(Modal):
    """Modal for seller to provide their wallet address"""
    def __init__(self, bot, escrow_id, seller_id, buyer_id, amount, crypto):
        super().__init__(title="Enter Your Wallet Address")
        self.bot = bot
        self.escrow_id = escrow_id
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.amount = amount
        self.crypto = crypto

        self.address_input = InputText(
            label=f"Your {crypto} Wallet Address",
            placeholder=f"Enter your {crypto} wallet address to receive payment",
            style=discord.InputTextStyle.short,
            required=True,
            min_length=10,
            max_length=200
        )
        self.add_item(self.address_input)

    async def callback(self, interaction: discord.Interaction):
        """Process fund release"""
        await interaction.response.defer()

        try:
            seller_address = self.address_input.value.strip()

            # Disable the button
            # Find the message with the "Enter My Wallet Address" button and disable it
            async for message in interaction.channel.history(limit=10):
                if message.components and len(message.components) > 0:
                    for component in message.components:
                        if hasattr(component, 'children'):
                            for child in component.children:
                                if hasattr(child, 'label') and 'Enter My Wallet Address' in str(child.label):
                                    view = View()
                                    button = Button(label="Processing...", style=discord.ButtonStyle.secondary, emoji="💳", disabled=True)
                                    view.add_item(button)
                                    await message.edit(view=view)
                                    break

            # Release funds via API
            api = self.bot.api_client
            result = await api.post(
                f"/api/v1/automm/{self.escrow_id}/release",
                data={"seller_address": seller_address},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            tx_hash = result.get("tx_hash")
            tx_url = result.get("tx_url")
            crypto_amount = result.get("amount", 0)
            crypto = result.get("crypto", self.crypto)

            # Show transaction details with full info
            if tx_hash and tx_url:
                tx_display = f"[View on Explorer]({tx_url})\n**TX Hash:** `{tx_hash}`"
            elif tx_hash:
                tx_display = f"**TX Hash:** `{tx_hash}`"
            else:
                tx_display = "Transaction submitted"

            # Success - funds released with full details
            embed = create_themed_embed(
                title="",
                description=(
                    f"## ✅ Funds Sent to Seller\n\n"
                    f"**Amount:** `{crypto_amount} {crypto}` (~${self.amount:.2f} USD)\n"
                    f"**To Address:** `{seller_address}`\n"
                    f"**Status:** Confirmed on blockchain ✅\n\n"
                    f"**Transaction Details:**\n"
                    f"{tx_display}\n\n"
                    f"## Final Step: Seller Confirmation\n\n"
                    f"**<@{self.seller_id}>** (Seller): Please check your wallet and confirm you received the payment by clicking the button below.\n\n"
                    f"**<@{self.buyer_id}>** (Buyer): Your funds have been released. Wait for seller confirmation.\n\n"
                    f"> The transaction is on the blockchain and cannot be reversed."
                ),
                color=PURPLE_GRADIENT
            )

            # Show confirmation view
            view = ConfirmationView(self.bot, self.escrow_id, self.seller_id, self.buyer_id)
            await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error releasing funds: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error releasing funds: {str(e)}", ephemeral=True)


class ConfirmationView(View):
    """View for seller to confirm receipt"""
    def __init__(self, bot, escrow_id, seller_id, buyer_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.escrow_id = escrow_id
        self.seller_id = seller_id
        self.buyer_id = buyer_id

    @discord.ui.button(label="I Received Payment", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_received_button(self, button, interaction):
        """Seller confirms received payment"""
        if interaction.user.id != self.seller_id:
            await interaction.response.send_message("❌ Only the seller can confirm receipt.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Mark as complete via API
            api = self.bot.api_client
            await api.post(
                f"/api/v1/automm/{self.escrow_id}/complete",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Success message with vouch instructions
            buyer_member = interaction.guild.get_member(int(self.buyer_id))
            seller_member = interaction.guild.get_member(int(self.seller_id))
            rep_channel_id = config.CHANNEL_REP
            rep_channel_mention = f"<#{rep_channel_id}>" if rep_channel_id else "#rep-channel"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## ✅ Escrow Complete\n\n"
                    f"Transaction completed successfully!\n\n"
                    f"## Vouch for Each Other\n\n"
                    f"Both parties can now vouch for each other in {rep_channel_mention}:\n\n"
                    f"**{buyer_member.mention if buyer_member else 'Buyer'} (Buyer):**\n"
                    f"```\n+rep @{self.bot.user.name} and @{seller_member.name if seller_member else 'Seller'} $AMOUNT AUTOMM\n```\n\n"
                    f"**{seller_member.mention if seller_member else 'Seller'} (Seller):**\n"
                    f"```\n+rep @{self.bot.user.name} and @{buyer_member.name if buyer_member else 'Buyer'} $AMOUNT AUTOMM\n```\n\n"
                    f"> Positive vouches build reputation in the community"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=embed)

            # Get members
            buyer_member = interaction.guild.get_member(int(self.buyer_id))
            seller_member = interaction.guild.get_member(int(self.seller_id))

            # Generate branded HTML transcript
            transcript_html = await generate_transcript(self.bot, interaction.channel, self.escrow_id, buyer_member, seller_member)

            # Upload transcript to URL
            transcript_url = await upload_transcript_to_url(self.escrow_id, transcript_html)

            # Post to transcript channel
            await post_transcript_to_channel(
                bot=self.bot,
                guild=interaction.guild,
                escrow_id=self.escrow_id,
                buyer_id=self.buyer_id,
                seller_id=self.seller_id,
                transcript_html=transcript_html
            )

            # Fetch escrow data for history
            escrow_data = None
            try:
                escrow_result = await api.get(
                    f"/api/v1/automm/{self.escrow_id}",
                    discord_user_id=str(self.buyer_id),
                    discord_roles=[]
                )
                escrow_data = escrow_result.get("escrow", {})
                logger.info(f"Fetched escrow data for history: {escrow_data.get('mm_id')}, {escrow_data.get('crypto')}, {escrow_data.get('amount')}")
            except Exception as e:
                logger.error(f"Failed to fetch escrow data for history: {e}")

            # Post to history channel
            await post_to_history(
                bot=self.bot,
                guild=interaction.guild,
                escrow_id=self.escrow_id,
                buyer_id=self.buyer_id,
                seller_id=self.seller_id,
                channel=interaction.channel,
                escrow_data=escrow_data
            )

            # DM both parties with vouch instructions and transcript
            await dm_buyer(buyer_member, seller_member, self.escrow_id, transcript_html, interaction.guild, interaction.channel.name, transcript_url)
            await dm_seller(seller_member, buyer_member, self.escrow_id, transcript_html, interaction.guild, interaction.channel.name, transcript_url)

            # Post vouch prompt to rep channel
            await post_to_rep_channel(
                guild=interaction.guild,
                buyer=buyer_member,
                seller=seller_member,
                escrow_id=self.escrow_id,
                bot=self.bot
            )

            # Close channel after delay
            await asyncio.sleep(60)
            await interaction.channel.delete(reason="Escrow completed")

        except Exception as e:
            logger.error(f"Error completing escrow: {e}", exc_info=True)
            await interaction.channel.send(f"❌ Error completing escrow: {str(e)}")


class BuyerRefundAddressView(View):
    """View for buyer to enter their wallet address for refund"""
    def __init__(self, bot, escrow_id, buyer_id, seller_id, amount, crypto):
        super().__init__(timeout=None)
        self.bot = bot
        self.escrow_id = escrow_id
        self.buyer_id = buyer_id
        self.seller_id = seller_id
        self.amount = amount
        self.crypto = crypto

    @discord.ui.button(label="Enter My Refund Address", style=discord.ButtonStyle.primary, emoji="💳")
    async def enter_refund_address_button(self, button, interaction):
        """Buyer clicks to open modal"""
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("❌ Only the buyer can enter their refund address.", ephemeral=True)
            return

        # Show modal to buyer
        modal = BuyerRefundAddressModal(self.bot, self.escrow_id, self.buyer_id, self.seller_id, self.amount, self.crypto)
        await interaction.response.send_modal(modal)


class BuyerRefundAddressModal(Modal):
    """Modal for buyer to provide their wallet address for refund"""
    def __init__(self, bot, escrow_id, buyer_id, seller_id, amount, crypto):
        super().__init__(title="Enter Your Refund Address")
        self.bot = bot
        self.escrow_id = escrow_id
        self.buyer_id = buyer_id
        self.seller_id = seller_id
        self.amount = amount
        self.crypto = crypto

        self.address_input = InputText(
            label=f"Your {crypto} Wallet Address",
            placeholder=f"Enter your {crypto} wallet address for refund",
            style=discord.InputTextStyle.short,
            required=True,
            min_length=10,
            max_length=200
        )
        self.add_item(self.address_input)

    async def callback(self, interaction: discord.Interaction):
        """Process refund"""
        await interaction.response.defer()

        try:
            buyer_address = self.address_input.value.strip()

            # Disable the button
            async for message in interaction.channel.history(limit=10):
                if message.components and len(message.components) > 0:
                    for component in message.components:
                        if hasattr(component, 'children'):
                            for child in component.children:
                                if hasattr(child, 'label') and 'Enter My Refund Address' in str(child.label):
                                    view = View()
                                    button = Button(label="Processing...", style=discord.ButtonStyle.secondary, emoji="💳", disabled=True)
                                    view.add_item(button)
                                    await message.edit(view=view)
                                    break

            # Process refund via API
            api = self.bot.api_client
            result = await api.post(
                f"/api/v1/automm/{self.escrow_id}/refund",
                data={"buyer_address": buyer_address},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles]
            )

            tx_hash = result.get("tx_hash")
            tx_url = result.get("tx_url")
            crypto_amount = result.get("amount", 0)
            crypto = result.get("crypto", self.crypto)

            # Show refund details
            if tx_hash and tx_url:
                tx_display = f"[View on Explorer]({tx_url})\n**TX Hash:** `{tx_hash}`"
            elif tx_hash:
                tx_display = f"**TX Hash:** `{tx_hash}`"
            else:
                tx_display = "Refund transaction submitted"

            # Success - refund processed
            embed = create_themed_embed(
                title="",
                description=(
                    f"## ✅ Refund Processed\n\n"
                    f"**Amount:** `{crypto_amount} {crypto}` (~${self.amount:.2f} USD)\n"
                    f"**To Address:** `{buyer_address}`\n"
                    f"**Status:** Confirmed on blockchain ✅\n\n"
                    f"**Transaction Details:**\n"
                    f"{tx_display}\n\n"
                    f"## Escrow Cancelled\n\n"
                    f"Both parties agreed to cancel this escrow.\n"
                    f"Funds have been returned to **<@{self.buyer_id}>** (Buyer).\n\n"
                    f"> This channel will close in 60 seconds."
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=embed)

            # Close channel after delay
            await asyncio.sleep(60)
            await interaction.channel.delete(reason="Escrow cancelled and refunded")

        except Exception as e:
            logger.error(f"Error processing refund: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error processing refund: {str(e)}", ephemeral=True)


async def generate_transcript(bot, channel, escrow_id, buyer_member, seller_member):
    """Generate branded HTML transcript using support_transcript system"""
    try:
        from utils.support_transcript import generate_support_transcript_html
        from datetime import datetime

        # Collect all messages
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append(message)

        # Get escrow details for MM ID
        try:
            api = bot.api_client
            escrow_result = await api.get(
                f"/api/v1/automm/{escrow_id}",
                discord_user_id=str(buyer_member.id if buyer_member else 0),
                discord_roles=[]
            )
            escrow = escrow_result.get("escrow", {})
            mm_id = escrow.get("mm_id", escrow_id[-8:].upper())
            created_at = escrow.get("created_at", "")

            # Parse created_at if it's a string
            if isinstance(created_at, str):
                try:
                    from dateutil import parser
                    opened_at = parser.parse(created_at)
                except:
                    opened_at = datetime.utcnow()
            else:
                opened_at = created_at or datetime.utcnow()
        except:
            mm_id = escrow_id[-8:].upper()
            opened_at = datetime.utcnow()

        # Generate HTML
        html_content = generate_support_transcript_html(
            ticket_number=int(mm_id, 16) % 100000,  # Convert hex to readable number
            ticket_type="AutoMM_Escrow",
            messages=messages,
            opened_by=buyer_member or channel.guild.me,
            closed_by=seller_member or channel.guild.me,
            opened_at=opened_at,
            closed_at=datetime.utcnow()
        )

        logger.info(f"Generated HTML transcript for escrow {escrow_id} ({len(messages)} messages)")

        # Return HTML content
        return html_content

    except Exception as e:
        logger.error(f"Error generating transcript: {e}", exc_info=True)
        return None


async def upload_transcript_to_url(escrow_id, transcript_html):
    """Upload HTML transcript to backend API at /api/v1/transcripts/upload"""
    if not transcript_html:
        return None

    try:
        import aiohttp
        import config

        # Backend API URL
        api_base = config.config.API_BASE_URL
        upload_url = f"{api_base}/api/v1/transcripts/upload"

        # Bot service token for authentication
        bot_token = config.config.BOT_SERVICE_TOKEN

        # Prepare upload data
        upload_data = {
            "ticket_id": escrow_id,
            "ticket_type": "automm",
            "ticket_number": None,
            "user_id": "system",  # AutoMM system-generated
            "participants": [],
            "html_content": transcript_html,
            "message_count": transcript_html.count("<div class=\"message\">") if transcript_html else 0
        }

        # Upload to backend API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                upload_url,
                json=upload_data,
                headers={
                    'X-Bot-Token': bot_token,
                    'Content-Type': 'application/json'
                }
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    public_url = result.get("public_url")
                    logger.info(f"Uploaded transcript to backend API: {public_url}")
                    return public_url
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to upload transcript: {response.status} - {error_text}")
                    return None

    except Exception as e:
        logger.error(f"Error uploading transcript to backend API: {e}", exc_info=True)
        return None


async def post_transcript_to_channel(bot, guild, escrow_id, buyer_id, seller_id, transcript_html):
    """Post HTML transcript to transcript channel"""
    if not transcript_html:
        return

    try:
        transcript_channel_id = config.transcript_channel
        if not transcript_channel_id:
            logger.warning("Transcript channel not configured")
            return

        transcript_channel = guild.get_channel(transcript_channel_id)
        if not transcript_channel:
            logger.warning(f"Transcript channel not found: {transcript_channel_id}")
            return

        # Get member info
        buyer = guild.get_member(int(buyer_id))
        seller = guild.get_member(int(seller_id))
        buyer_name = buyer.name if buyer else "Unknown"
        seller_name = seller.name if seller else "Unknown"

        # Get escrow details from API
        api = bot.api_client
        try:
            escrow_result = await api.get(
                f"/api/v1/automm/{escrow_id}",
                discord_user_id=str(buyer_id),
                discord_roles=[]
            )
            escrow = escrow_result.get("escrow", {})
            mm_id = escrow.get("mm_id", escrow_id[-8:].upper())
            crypto = escrow.get("crypto", "N/A")
            amount = escrow.get("amount", 0)
            created_at = escrow.get("created_at", "")

            # Parse created_at if it's a string
            if isinstance(created_at, str) and created_at:
                try:
                    from dateutil import parser
                    created_datetime = parser.parse(created_at)
                    date_str = created_datetime.strftime('%B %d, %Y at %I:%M %p UTC')
                except:
                    date_str = "Unknown"
            else:
                date_str = "Unknown"
        except:
            mm_id = escrow_id[-8:].upper()
            crypto = "N/A"
            amount = 0
            date_str = "Unknown"

        # Create transcript embed
        embed = create_themed_embed(
            title="",
            description=(
                f"## 📝 AutoMM Escrow Transcript - MM #{mm_id}\n\n"
                f"**Buyer:** {buyer.mention if buyer else 'Unknown'} (`{buyer_name}`)\n"
                f"**Seller:** {seller.mention if seller else 'Unknown'} (`{seller_name}`)\n"
                f"**Amount:** `${amount:.2f} USD` in **{crypto}**\n\n"
                f"**Completed:** {date_str}"
            ),
            color=PURPLE_GRADIENT
        )

        # Create HTML file
        import io
        html_file = discord.File(
            io.BytesIO(transcript_html.encode('utf-8')),
            filename=f"AutoMM_Escrow_{mm_id}.html"
        )

        # Post to transcript channel
        await transcript_channel.send(embed=embed, file=html_file)

        logger.info(f"Posted transcript for escrow {escrow_id} to transcript channel")

    except Exception as e:
        logger.error(f"Error posting transcript to channel: {e}", exc_info=True)


async def post_to_history(bot, guild, escrow_id, buyer_id, seller_id, channel, escrow_data=None):
    """Post completed escrow to history channel"""
    try:
        history_channel_id = config.CHANNEL_EXCHANGE_HISTORY
        if not history_channel_id:
            logger.warning("Exchange history channel not configured")
            return

        history_channel = guild.get_channel(history_channel_id)
        if not history_channel:
            logger.warning(f"History channel not found: {history_channel_id}")
            return

        # Get member info
        buyer = guild.get_member(int(buyer_id))
        seller = guild.get_member(int(seller_id))
        buyer_name = buyer.name if buyer else "Unknown"
        seller_name = seller.name if seller else "Unknown"

        # Get escrow details - prefer passed data, fallback to API
        if escrow_data:
            mm_id = escrow_data.get("mm_id", "N/A")
            crypto = escrow_data.get("crypto", "N/A")
            amount = escrow_data.get("amount", 0)
            service = escrow_data.get("service_description", "N/A")
            logger.info(f"Using provided escrow data for history: mm_id={mm_id}, crypto={crypto}, amount={amount}, service={service}")
        else:
            # Fallback: Fetch from API
            api = bot.api_client
            try:
                escrow_result = await api.get(
                    f"/api/v1/automm/{escrow_id}",
                    discord_user_id=str(buyer_id),
                    discord_roles=[]
                )
                escrow = escrow_result.get("escrow", {})
                mm_id = escrow.get("mm_id", "N/A")
                crypto = escrow.get("crypto", "N/A")
                amount = escrow.get("amount", 0)
                service = escrow.get("service_description", "N/A")
                logger.info(f"Fetched escrow data from API for history: mm_id={mm_id}, crypto={crypto}, amount={amount}, service={service}")
            except Exception as e:
                logger.error(f"Error fetching escrow data from API for history embed: {e}", exc_info=True)
                mm_id = escrow_id[-8:].upper()
                crypto = "N/A"
                amount = 0
                service = "N/A"

        # Create history embed with PURPLE_GRADIENT
        embed = create_themed_embed(
            title="",
            description=(
                f"## 🤝 AutoMM Escrow Completed - MM #{mm_id}\n\n"
                f"**Buyer:** <@{buyer_id}> (`{buyer_name}`)\n"
                f"**Seller:** <@{seller_id}> (`{seller_name}`)\n\n"
                f"**Service:** {service}\n"
                f"**Amount:** `${amount:.2f} USD` in **{crypto}**"
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Escrow ID: {escrow_id} | MM #{mm_id}")
        embed.timestamp = discord.utils.utcnow()

        await history_channel.send(embed=embed)

        logger.info(f"Posted escrow {escrow_id} to history channel")

    except Exception as e:
        logger.error(f"Error posting to history: {e}", exc_info=True)


async def dm_buyer(buyer, seller, escrow_id, transcript_html, guild, channel_name, transcript_url=None):
    """Send DM to buyer with vouch instructions"""
    if not buyer:
        return

    try:
        rep_channel_id = config.CHANNEL_REP
        rep_mention = f"<#{rep_channel_id}>" if rep_channel_id else "#rep-channel"

        # Add transcript URL to description if available
        transcript_line = f"\n**Transcript URL:** {transcript_url}\n" if transcript_url else ""

        embed = create_themed_embed(
            title="",
            description=(
                f"## ✅ Escrow Completed!\n\n"
                f"Your escrow transaction has been completed successfully!\n\n"
                f"**Escrow ID:** `{escrow_id}`\n"
                f"**Seller:** {seller.mention if seller else 'Unknown'}{transcript_line}\n"
                f"---\n\n"
                f"### Please Vouch in {rep_mention}\n\n"
                f"**Format:**\n"
                f"```\n+rep @{guild.me.name} and @{seller.name if seller else 'Seller'} $AMOUNT AUTOMM\n```\n\n"
                f"**Example:**\n"
                f"```\n+rep @{guild.me.name} and @{seller.name if seller else 'Seller'} $50 AUTOMM\n```\n\n"
                f"---\n\n"
                f"Thank you for using **Afroo AutoMM Escrow**!"
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Escrow ID: {escrow_id} | Afroo AutoMM")

        await buyer.send(embed=embed)

        # Send branded HTML transcript
        if transcript_html:
            import io
            transcript_file = io.BytesIO(transcript_html.encode('utf-8'))
            await buyer.send(
                content="📝 **Escrow Transcript** (Open in browser for best experience)",
                file=discord.File(transcript_file, filename=f"AutoMM_Escrow_{escrow_id[-8:]}.html")
            )

        logger.info(f"Sent completion DM to buyer {buyer.id}")

    except discord.Forbidden:
        logger.warning(f"Could not DM buyer {buyer.id} - DMs disabled")
    except Exception as e:
        logger.error(f"Error sending buyer DM: {e}", exc_info=True)


async def dm_seller(seller, buyer, escrow_id, transcript_html, guild, channel_name, transcript_url=None):
    """Send DM to seller with completion details"""
    if not seller:
        return

    try:
        rep_channel_id = config.CHANNEL_REP
        rep_mention = f"<#{rep_channel_id}>" if rep_channel_id else "#rep-channel"

        # Add transcript URL to description if available
        transcript_line = f"\n**Transcript URL:** {transcript_url}\n" if transcript_url else ""

        embed = create_themed_embed(
            title="",
            description=(
                f"## ✅ Escrow Completed\n\n"
                f"Escrow transaction has been completed!\n\n"
                f"**Escrow ID:** `{escrow_id}`\n"
                f"**Buyer:** {buyer.mention if buyer else 'Unknown'}{transcript_line}\n"
                f"Funds have been released to your wallet.\n\n"
                f"---\n\n"
                f"### Please Vouch in {rep_mention}\n\n"
                f"**Format:**\n"
                f"```\n+rep @{guild.me.name} and @{buyer.name if buyer else 'Buyer'} $AMOUNT AUTOMM\n```\n\n"
                f"**Example:**\n"
                f"```\n+rep @{guild.me.name} and @{buyer.name if buyer else 'Buyer'} $50 AUTOMM\n```\n\n"
                f"---\n\n"
                f"Thank you for using **Afroo AutoMM Escrow**!"
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Escrow ID: {escrow_id} | Afroo AutoMM")

        await seller.send(embed=embed)

        # Send branded HTML transcript
        if transcript_html:
            import io
            transcript_file = io.BytesIO(transcript_html.encode('utf-8'))
            await seller.send(
                content="📝 **Escrow Transcript** (Open in browser for best experience)",
                file=discord.File(transcript_file, filename=f"AutoMM_Escrow_{escrow_id[-8:]}.html")
            )

        logger.info(f"Sent completion DM to seller {seller.id}")

    except discord.Forbidden:
        logger.warning(f"Could not DM seller {seller.id} - DMs disabled")
    except Exception as e:
        logger.error(f"Error sending seller DM: {e}", exc_info=True)


async def post_to_rep_channel(guild, buyer, seller, escrow_id, bot):
    """Post completion announcement to rep channel"""
    try:
        # Get rep channel from config
        rep_channel_id = config.CHANNEL_REP
        if not rep_channel_id:
            logger.warning("Rep channel not configured")
            return

        rep_channel = guild.get_channel(rep_channel_id)
        if not rep_channel:
            logger.warning(f"Rep channel not found: {rep_channel_id}")
            return

        # Get escrow details
        api = bot.api_client
        try:
            escrow_result = await api.get(
                f"/api/v1/automm/{escrow_id}",
                discord_user_id=str(buyer.id if buyer else 0),
                discord_roles=[]
            )
            escrow = escrow_result.get("escrow", {})
            mm_id = escrow.get("mm_id", "N/A")
            amount = escrow.get("amount", 0)
            channel_id = escrow.get("channel_id", "")
        except:
            mm_id = "N/A"
            amount = 0
            channel_id = ""

        # Simple announcement
        await rep_channel.send(
            f"🤝 **AutoMM Escrow Completed - MM #{mm_id}**\n\n"
            f"{buyer.mention if buyer else 'Buyer'} ↔️ {seller.mention if seller else 'Seller'} | `${amount:.2f} USD`\n\n"
            f"Vouch in <#{channel_id}>" if channel_id else ""
        )

        logger.info(f"Posted completion announcement to rep channel for escrow {escrow_id}")

    except Exception as e:
        logger.error(f"Error posting to rep channel: {e}", exc_info=True)
