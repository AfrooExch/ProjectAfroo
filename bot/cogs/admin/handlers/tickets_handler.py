"""Admin Tickets Handler"""
import logging
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)

async def show_all_tickets(interaction, bot):
    """Show all active tickets"""
    api = bot.api_client
    try:
        tickets = await api.get("/api/v1/admin/tickets/all")
        if not tickets:
            await interaction.followup.send("📋 No active tickets.", ephemeral=True)
            return

        tickets_text = ""
        for t in tickets[:20]:
            ticket_id = t.get("id", "")[:8]
            status = t.get("status", "unknown")
            ticket_type = t.get("type", "exchange")
            tickets_text += f"• `{ticket_id}` - {ticket_type} - {status}\n"

        embed = create_themed_embed(title="", description=f"## 🎫 All Tickets\n\n**Total:** {len(tickets)}\n\n{tickets_text}", color=PURPLE_GRADIENT)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
