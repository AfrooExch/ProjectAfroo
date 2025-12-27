"""Admin Holds Management Handler"""
import logging
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)

async def show_all_holds(interaction, bot):
    """Show all active fund holds"""
    from utils.auth import get_user_context
    api = bot.api_client
    try:
        user_context_id, roles = get_user_context(interaction)
        holds = await api.get(
            "/api/v1/admin/holds/all",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )
        if not holds:
            await interaction.followup.send("🔒 No active holds.", ephemeral=True)
            return

        holds_text = ""
        for h in holds[:15]:
            user_id = h.get("user_id", "")
            asset = h.get("asset", "")
            amount = h.get("amount_units", 0)
            ticket_id = h.get("ticket_id", "")[:8]
            holds_text += f"• User `{user_id}` - `{amount:.4f} {asset}` - Ticket `{ticket_id}`\n"

        embed = create_themed_embed(title="", description=f"## 🔒 Active Holds\n\n**Total:** {len(holds)}\n\n{holds_text}", color=PURPLE_GRADIENT)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
