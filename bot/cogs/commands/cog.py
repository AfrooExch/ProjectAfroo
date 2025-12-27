"""
Commands Cog
Loads portable panel commands
"""

from .portable_panels import PortablePanels


def setup(bot):
    """Setup function called by Discord.py"""
    bot.add_cog(PortablePanels(bot))
