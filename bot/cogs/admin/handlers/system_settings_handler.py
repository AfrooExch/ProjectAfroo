"""
Admin System Settings Handler
Database backup triggers and system information
HEAD ADMIN ONLY
"""

import logging
import discord
from discord.ui import View, Button

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, WARNING

logger = logging.getLogger(__name__)


async def show_system_settings(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Display system settings and information with database backup triggers

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get system info from backend
        system_info = await api.get(
            "/api/v1/admin/system/info",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        info = system_info.get("data", {})
        version = info.get("version", "Unknown")
        environment = info.get("environment", "Unknown")
        uptime = info.get("uptime_hours", 0)
        database_size_mb = info.get("database_size_mb", 0)
        last_backup = info.get("last_backup", "Never")
        scheduled_tasks = info.get("scheduled_tasks", [])

        # Build scheduled tasks list
        tasks_text = ""
        if scheduled_tasks:
            for task in scheduled_tasks:
                task_name = task.get("name", "Unknown")
                task_schedule = task.get("schedule", "Unknown")
                task_status = task.get("status", "Unknown")
                tasks_text += f"> • **{task_name}**: {task_schedule} ({task_status})\n"
        else:
            tasks_text = "> No scheduled tasks available"

        embed = create_themed_embed(
            title="",
            description=(
                f"## ⚙️ System Settings\n\n"
                f"### System Information\n\n"
                f"**Version:** `{version}`\n"
                f"**Environment:** `{environment}`\n"
                f"**Uptime:** `{uptime:.1f} hours`\n"
                f"**Database Size:** `{database_size_mb:.2f} MB`\n"
                f"**Last Backup:** `{last_backup}`\n\n"
                f"### Scheduled Tasks\n\n"
                f"{tasks_text}\n\n"
                f"### Database Backups\n\n"
                f"> • **Local Backup**: Creates .gz dump in `/backups/` directory\n"
                f"> • **Cloud Backup**: Uploads to configured cloud storage\n"
                f"> • **Auto-Backup**: Runs every 6 hours automatically\n"
                f"> • Use buttons below to trigger manual backup\n\n"
                f"> 💡 Regular backups protect against data loss\n"
                f"> 💡 Store backups securely offsite"
            ),
            color=PURPLE_GRADIENT
        )

        # Add action buttons (HEAD ADMIN only)
        HEAD_ADMIN_ID = 1419744557054169128
        view = None
        if interaction.user.id == HEAD_ADMIN_ID:
            view = SystemSettingsView(bot)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed system settings to admin {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error loading system info: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading System Info",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing system settings: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load system settings: {str(e)}"
            ),
            ephemeral=True
        )


class SystemSettingsView(View):
    """View with buttons for system settings actions (HEAD ADMIN ONLY)"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Local Backup",
        style=discord.ButtonStyle.primary,
        emoji="💾"
    )
    async def local_backup_button(self, button: Button, interaction: discord.Interaction):
        """Trigger local database backup"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Trigger local backup
            result = await api.post(
                "/api/v1/admin/system/backup-database?backup_type=local",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            backup_data = result.get("data", {})
            backup_name = backup_data.get("backup_name", "Unknown")
            backup_size_mb = backup_data.get("backup_size_mb", 0)
            backup_path = backup_data.get("backup_path", "Unknown")

            embed = create_success_embed(
                title="Local Backup Complete",
                description=(
                    f"## Database Backup Created\n\n"
                    f"**Backup Name:** `{backup_name}`\n"
                    f"**Size:** `{backup_size_mb:.2f} MB`\n"
                    f"**Location:** `{backup_path}`\n\n"
                    f"### Next Steps\n\n"
                    f"> • Download backup from server if needed\n"
                    f"> • Store securely offsite\n"
                    f"> • Verify backup integrity\n\n"
                    f"> 💡 Backup contains full MongoDB dump\n"
                    f"> 💡 Accessible from backend container"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} triggered local backup: {backup_name}")

        except APIError as e:
            logger.error(f"API error during local backup: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Backup Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during local backup: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to create backup: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Cloud Backup",
        style=discord.ButtonStyle.primary,
        emoji="☁️"
    )
    async def cloud_backup_button(self, button: Button, interaction: discord.Interaction):
        """Trigger cloud database backup"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Trigger cloud backup
            result = await api.post(
                "/api/v1/admin/system/backup-database?backup_type=cloud",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            backup_data = result.get("data", {})
            backup_name = backup_data.get("backup_name", "Unknown")
            backup_size_mb = backup_data.get("backup_size_mb", 0)
            cloud_url = backup_data.get("cloud_url", "N/A")

            embed = create_success_embed(
                title="Cloud Backup Complete",
                description=(
                    f"## Database Backup Uploaded\n\n"
                    f"**Backup Name:** `{backup_name}`\n"
                    f"**Size:** `{backup_size_mb:.2f} MB`\n"
                    f"**Cloud Storage:** `{cloud_url}`\n\n"
                    f"### Backup Details\n\n"
                    f"> • Uploaded to configured cloud storage\n"
                    f"> • Encrypted in transit\n"
                    f"> • Accessible for disaster recovery\n\n"
                    f"> 💡 Cloud backups provide offsite redundancy\n"
                    f"> 💡 Verify cloud storage access regularly"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} triggered cloud backup: {backup_name}")

        except APIError as e:
            logger.error(f"API error during cloud backup: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Cloud Backup Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during cloud backup: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to upload backup: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Backup History",
        style=discord.ButtonStyle.secondary,
        emoji="📜"
    )
    async def backup_history_button(self, button: Button, interaction: discord.Interaction):
        """View backup history"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get backup history
            result = await api.get(
                "/api/v1/admin/system/backup-history?limit=10",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            history_data = result.get("data", [])

            # Build history text
            history_text = ""
            if history_data:
                for idx, backup in enumerate(history_data, 1):
                    backup_name = backup.get("backup_name", "Unknown")
                    backup_type = backup.get("backup_type", "Unknown")
                    size_mb = backup.get("size_mb", 0)
                    created_at = backup.get("created_at", "Unknown")
                    status = backup.get("status", "Unknown")

                    status_emoji = "" if status == "success" else ""

                    history_text += (
                        f"**{idx}.** {status_emoji} `{backup_name}`\n"
                        f"   Type: {backup_type} | Size: {size_mb:.2f} MB | {created_at}\n"
                    )
            else:
                history_text = "> No backup history available"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 📜 Backup History\n\n"
                    f"### Recent Backups (Last 10)\n\n"
                    f"{history_text}\n\n"
                    f"> 💡 Showing most recent backups\n"
                    f"> 💡 Older backups stored in backend logs"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Head Admin {interaction.user.id} viewed backup history")

        except APIError as e:
            logger.error(f"API error loading backup history: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error Loading History",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error loading backup history: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to load backup history: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Restart Services",
        style=discord.ButtonStyle.danger,
        emoji=""
    )
    async def restart_services_button(self, button: Button, interaction: discord.Interaction):
        """Restart backend services"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "**Warning**\n\nService restart functionality requires manual server access.\n\n"
            "To restart services:\n"
            "1. SSH into your server\n"
            "2. Run: `docker restart afroo-backend-dev`\n"
            "3. Monitor logs: `docker logs -f afroo-backend-dev`\n\n"
            "> This prevents accidental service disruption",
            ephemeral=True
        )

        logger.info(f"Head Admin {interaction.user.id} requested restart info")
