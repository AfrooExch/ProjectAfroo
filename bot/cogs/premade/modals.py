"""
Premade Modals
Modal for creating premade messages
"""

import discord


class CreatePremadeModal(discord.ui.Modal):
    """Modal for creating a new premade message"""

    def __init__(self):
        super().__init__(title="Create Premade Message")

        self.add_item(
            discord.ui.InputText(
                label="Name",
                placeholder="e.g., BTC Wallet, PayPal Info, TOS",
                style=discord.InputTextStyle.short,
                max_length=50,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Content",
                placeholder="Enter the premade message content...",
                style=discord.InputTextStyle.long,
                max_length=1900,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission"""
        from api.client import APIClient
        from api.errors import APIError
        from utils.embeds import create_themed_embed
        from utils.colors import GREEN_GRADIENT, RED_GRADIENT

        name = self.children[0].value
        content = self.children[1].value

        bot = interaction.client
        api: APIClient = bot.api_client

        try:
            # Create premade via API
            response = await api.post(
                "/api/v1/exchanger/premades",
                data={
                    "name": name,
                    "content": content
                },
                discord_user_id=str(interaction.user.id)
            )

            if response.get("success"):
                embed = create_themed_embed(
                    title="Premade Created",
                    description=f"Successfully created premade **{name}**",
                    color=GREEN_GRADIENT
                )
                embed.add_field(name="Name", value=name, inline=False)
                embed.add_field(name="Content Preview", value=content[:200] + ("..." if len(content) > 200 else ""), inline=False)

                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                error_msg = response.get("message", "Unknown error")
                embed = create_themed_embed(
                    title="Failed to Create Premade",
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
