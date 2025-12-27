"""Utils package - Shared utilities"""

from utils.colors import *
from utils.embeds import *
from utils.formatting import *
from utils.decorators import *
from utils.view_manager import ViewManager, PersistentView
from utils.auth import (
    get_user_context,
    get_member_context,
    handle_api_errors,
    is_admin,
    is_staff,
    is_exchanger,
    require_admin,
    require_staff,
    require_exchanger,
    APIContext
)
from utils.qr_generator import (
    generate_qr_code,
    generate_qr_for_btc,
    generate_qr_for_eth,
    generate_qr_for_ltc,
    generate_qr_for_sol,
    create_qr_discord_file,
    is_qr_available
)
