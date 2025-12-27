"""
Premade Views
Views and buttons for premade message system
"""

import discord
from typing import List, Dict
import logging

from api.client import APIClient
from api.errors import APIError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, GREEN_GRADIENT, RED_GRADIENT
from cogs.premade.modals import CreatePremadeModal

logger = logging.getLogger(__name__)


class PremadePanelView(discord.ui.View):
    """Main premade panel with Create and Send buttons"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Premade", style=discord.ButtonStyle.primary, emoji="➕")
    async def create_premade_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open modal to create a new premade"""
        modal = CreatePremadeModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Send Premade", style=discord.ButtonStyle.success, emoji="📤")
    async def send_premade_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show dropdown to select and send a premade"""
        bot = interaction.client
        api: APIClient = bot.api_client

        try:
            # Get premades from API
            response = await api.get(
                "/api/v1/exchanger/premades",
                discord_user_id=str(interaction.user.id)
            )

            if not response.get("success"):
                embed = create_themed_embed(
                    title="Error",
                    description="Failed to load premades",
                    color=RED_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            premades = response.get("premades", [])

            if not premades:
                embed = create_themed_embed(
                    title="No Premades",
                    description="You don't have any premades yet. Click **Create Premade** to get started!",
                    color=PURPLE_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Show select menu
            view = PremadeSelectView(premades, interaction.channel)
            embed = create_themed_embed(
                title="Select Premade",
                description="Choose a premade message to send in this channel",
                color=PURPLE_GRADIENT
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except APIError as e:
            embed = create_themed_embed(
                title="Error",
                description=str(e),
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Manage Premades", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def manage_premades_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show list of premades with delete options"""
        bot = interaction.client
        api: APIClient = bot.api_client

        try:
            # Get premades from API
            response = await api.get(
                "/api/v1/exchanger/premades",
                discord_user_id=str(interaction.user.id)
            )

            if not response.get("success"):
                embed = create_themed_embed(
                    title="Error",
                    description="Failed to load premades",
                    color=RED_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            premades = response.get("premades", [])

            if not premades:
                embed = create_themed_embed(
                    title="No Premades",
                    description="You don't have any premades yet. Click **Create Premade** to get started!",
                    color=PURPLE_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Show manage view
            view = ManagePremadesView(premades)
            embed = create_themed_embed(
                title="Manage Premades",
                description=f"You have **{len(premades)}** premade(s). Select one to delete:",
                color=PURPLE_GRADIENT
            )

            # Add premade list
            for premade in premades[:10]:  # Show max 10
                name = premade.get("name")
                content = premade.get("content", "")
                preview = content[:100] + ("..." if len(content) > 100 else "")
                embed.add_field(name=f"📝 {name}", value=preview, inline=False)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except APIError as e:
            embed = create_themed_embed(
                title="Error",
                description=str(e),
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class PremadeSelectView(discord.ui.View):
    """View with dropdown to select a premade to send"""

    def __init__(self, premades: List[Dict], channel: discord.TextChannel):
        super().__init__(timeout=180)  # 3 minute timeout
        self.premades = premades
        self.channel = channel
        self.add_item(PremadeSelectMenu(premades, channel))


class PremadeSelectMenu(discord.ui.Select):
    """Dropdown menu to select a premade"""

    def __init__(self, premades: List[Dict], channel: discord.TextChannel):
        self.premades = premades
        self.channel = channel

        # Create options from premades
        options = []
        for premade in premades[:25]:  # Discord max 25 options
            name = premade.get("name")
            content = premade.get("content", "")
            description = content[:100] if len(content) <= 100 else content[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=name,
                    description=description,
                    value=name
                )
            )

        super().__init__(
            placeholder="Select a premade message...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        """Send the selected premade"""
        selected_name = self.values[0]

        # Find the premade
        premade = next((p for p in self.premades if p.get("name") == selected_name), None)

        if not premade:
            embed = create_themed_embed(
                title="Error",
                description="Premade not found",
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        content = premade.get("content", "")

        try:
            # Send the premade message to the channel
            await self.channel.send(content)

            # Confirm to user
            embed = create_themed_embed(
                title="Premade Sent",
                description=f"Successfully sent **{selected_name}** to {self.channel.mention}",
                color=GREEN_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            logger.info(f"User {interaction.user.id} sent premade '{selected_name}' to channel {self.channel.id}")

        except discord.Forbidden:
            embed = create_themed_embed(
                title="Permission Error",
                description="I don't have permission to send messages in that channel",
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending premade: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description="Failed to send premade message",
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class ManagePremadesView(discord.ui.View):
    """View with dropdown to delete premades"""

    def __init__(self, premades: List[Dict]):
        super().__init__(timeout=180)
        self.premades = premades
        self.add_item(DeletePremadeMenu(premades))


class DeletePremadeMenu(discord.ui.Select):
    """Dropdown menu to delete a premade"""

    def __init__(self, premades: List[Dict]):
        self.premades = premades

        # Create options from premades
        options = []
        for premade in premades[:25]:  # Discord max 25 options
            name = premade.get("name")
            content = premade.get("content", "")
            description = content[:100] if len(content) <= 100 else content[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=name,
                    description=description,
                    value=name,
                    emoji="🗑️"
                )
            )

        super().__init__(
            placeholder="Select a premade to delete...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        """Delete the selected premade"""
        selected_name = self.values[0]

        bot = interaction.client
        api: APIClient = bot.api_client

        try:
            # Delete via API
            response = await api.delete(
                f"/api/v1/exchanger/premades/{selected_name}",
                discord_user_id=str(interaction.user.id)
            )

            if response.get("success"):
                embed = create_themed_embed(
                    title="Premade Deleted",
                    description=f"Successfully deleted **{selected_name}**",
                    color=GREEN_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

                logger.info(f"User {interaction.user.id} deleted premade '{selected_name}'")
            else:
                error_msg = response.get("message", "Unknown error")
                embed = create_themed_embed(
                    title="Failed to Delete",
                    description=error_msg,
                    color=RED_GRADIENT
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except APIError as e:
            embed = create_themed_embed(
                title="Error",
                description=str(e),
                color=RED_GRADIENT
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
