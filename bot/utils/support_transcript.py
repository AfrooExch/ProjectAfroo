"""
Support Ticket Transcript Generator
Creates beautiful HTML transcripts of support ticket conversations
"""

import discord
import base64
import re
from datetime import datetime
from typing import List
from pathlib import Path


def parse_discord_content(content: str, guild: discord.Guild = None) -> str:
    """Parse Discord markdown and mentions to clean HTML"""
    if not content:
        return ""

    # Replace user mentions <@123456> with usernames
    def replace_mention(match):
        user_id = match.group(1)
        if guild:
            try:
                member = guild.get_member(int(user_id))
                if member:
                    return f'<span class="mention">@{member.display_name}</span>'
            except:
                pass
        return f'<span class="mention">@User</span>'

    content = re.sub(r'<@!?(\d+)>', replace_mention, content)

    # Replace role mentions <@&123456>
    def replace_role_mention(match):
        role_id = match.group(1)
        if guild:
            try:
                role = guild.get_role(int(role_id))
                if role:
                    return f'<span class="mention">@{role.name}</span>'
            except:
                pass
        return f'<span class="mention">@Role</span>'

    content = re.sub(r'<@&(\d+)>', replace_role_mention, content)

    # Replace channel mentions <#123456>
    def replace_channel_mention(match):
        channel_id = match.group(1)
        if guild:
            try:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    return f'<span class="mention">#{channel.name}</span>'
            except:
                pass
        return f'<span class="mention">#channel</span>'

    content = re.sub(r'<#(\d+)>', replace_channel_mention, content)

    # Parse markdown formatting
    # Bold **text**
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)

    # Italic *text* or _text_
    content = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', content)
    content = re.sub(r'_(.+?)_', r'<em>\1</em>', content)

    # Strikethrough ~~text~~
    content = re.sub(r'~~(.+?)~~', r'<del>\1</del>', content)

    # Underline __text__
    content = re.sub(r'__(.+?)__', r'<u>\1</u>', content)

    # Code blocks ```text```
    content = re.sub(r'```(.+?)```', r'<code>\1</code>', content, flags=re.DOTALL)

    # Inline code `text`
    content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)

    # Replace newlines with <br>
    content = content.replace('\n', '<br>')

    return content


def get_logo_base64() -> str:
    """Get logo as base64 data URI"""
    try:
        logo_path = Path(__file__).parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                logo_data = base64.b64encode(f.read()).decode()
                return f"data:image/png;base64,{logo_data}"
    except Exception as e:
        print(f"Failed to load logo: {e}")

    # Fallback to placeholder
    return ""


def generate_support_transcript_html(
    ticket_number: int,
    ticket_type: str,
    messages: List[discord.Message],
    opened_by: discord.User,
    closed_by: discord.User,
    opened_at: datetime,
    closed_at: datetime
) -> str:
    """Generate professional HTML transcript for a support ticket with Afroo theme"""

    # Get guild for mention parsing
    guild = messages[0].guild if messages else None

    # Get logo
    logo_data_uri = get_logo_base64()

    # Build message HTML with collapsible blocks
    messages_html = ""
    msg_count = 0
    for msg in messages:
        # Skip system messages
        if msg.type != discord.MessageType.default:
            continue

        msg_count += 1
        timestamp = msg.created_at.strftime("%B %d, %Y at %I:%M %p UTC")
        timestamp_short = msg.created_at.strftime("%I:%M %p")
        author_name = msg.author.display_name
        author_username = str(msg.author)
        author_id = str(msg.author.id)
        author_avatar = msg.author.display_avatar.url
        author_created = msg.author.created_at.strftime("%B %d, %Y")

        # Parse message content
        content = parse_discord_content(msg.content, guild) if msg.content else '<span class="no-content">No text content</span>'

        # Add embeds if any
        embeds_html = ""
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description:
                    parsed_embed = parse_discord_content(embed.description, guild)
                    embeds_html += f'<div class="embed-content">{parsed_embed}</div>'

        # Add attachments if any
        attachments_html = ""
        if msg.attachments:
            for attachment in msg.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    attachments_html += f'<div class="attachment-item"><img src="{attachment.url}" alt="attachment" /></div>'
                else:
                    attachments_html += f'<div class="attachment-item"><a href="{attachment.url}" target="_blank">📎 {attachment.filename}</a></div>'

        messages_html += f'''
        <div class="message-block" data-search-content="{author_name.lower()} {author_username.lower()} {msg.content.lower() if msg.content else ''}">
            <div class="message-divider"></div>
            <div class="message-container">
                <div class="avatar-container">
                    <img src="{author_avatar}" alt="avatar" class="avatar-badge" />
                </div>
                <div class="message-body">
                    <div class="message-header-bar">
                        <div class="author-info" onclick="toggleUserInfo(this)">
                            <span class="author-name">{author_name}</span>
                            <span class="timestamp-text">{timestamp_short}</span>
                        </div>
                        <button class="collapse-btn" onclick="toggleMessage(this)" title="Collapse message">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M3 5l5 5 5-5H3z"/>
                            </svg>
                        </button>
                    </div>
                    <div class="user-dropdown">
                        <div class="user-dropdown-grid">
                            <div class="dropdown-item">
                                <span class="dropdown-label">User ID</span>
                                <span class="dropdown-value">{author_id}</span>
                            </div>
                            <div class="dropdown-item">
                                <span class="dropdown-label">Username</span>
                                <span class="dropdown-value">@{author_username}</span>
                            </div>
                            <div class="dropdown-item">
                                <span class="dropdown-label">Display Name</span>
                                <span class="dropdown-value">{author_name}</span>
                            </div>
                            <div class="dropdown-item">
                                <span class="dropdown-label">Account Created</span>
                                <span class="dropdown-value">{author_created}</span>
                            </div>
                        </div>
                    </div>
                    <div class="message-content-area">
                        {content}
                        {embeds_html}
                        {attachments_html}
                    </div>
                </div>
            </div>
        </div>
        '''

    # Logo HTML
    logo_html = f'<img src="{logo_data_uri}" alt="Afroo Exchange" class="header-logo" />' if logo_data_uri else '<div class="header-logo-text">AE</div>'

    # Ticket type for badge
    ticket_type_display = ticket_type.replace('_', ' ').title()

    # Determine document type based on ticket type
    is_application = "application" in ticket_type.lower() or ticket_type.lower() == "exchanger_application"
    is_exchange = "exchange" in ticket_type.lower() or ticket_type.lower() == "exchange_ticket"
    is_automm = "automm" in ticket_type.lower()

    if is_application:
        document_type = "Exchanger Application"
    elif is_exchange:
        document_type = "Exchange Transcript"
    elif is_automm:
        document_type = "AutoMM Escrow"
    else:
        document_type = "Support Ticket"

    # Build full HTML with Afroo theme
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{document_type} #{ticket_number} - Afroo Exchange</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #0a0a15;
            color: #ffffff;
            line-height: 1.6;
            overflow-x: hidden;
        }}

        /* Sticky Navigation Bar */
        .top-nav {{
            position: sticky;
            top: 0;
            z-index: 1000;
            background: rgba(20, 10, 30, 0.6);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(155, 89, 255, 0.3);
            padding: 15px 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
        }}

        .nav-title {{
            font-size: 18px;
            font-weight: 600;
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .search-container {{
            flex: 1;
            max-width: 500px;
        }}

        .search-bar {{
            width: 100%;
            padding: 10px 16px;
            background: rgba(30, 20, 50, 0.55);
            border: 1px solid rgba(155, 89, 255, 0.25);
            border-radius: 8px;
            color: #ffffff;
            font-size: 14px;
            outline: none;
            transition: 0.25s ease;
            caret-color: #9B59FF;
        }}

        .search-bar:focus {{
            border-color: #9B59FF;
            box-shadow: 0 0 8px rgba(155, 89, 255, 0.4);
        }}

        .search-bar::placeholder {{
            color: rgba(191, 191, 220, 0.5);
        }}

        /* Main Layout */
        .main-layout {{
            display: flex;
            max-width: 1800px;
            margin: 0 auto;
            gap: 25px;
            padding: 25px;
        }}

        /* Content Area */
        .content-area {{
            flex: 1;
            min-width: 0;
        }}

        /* Header with GFX */
        .header-section {{
            position: relative;
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.6)),
                        linear-gradient(135deg, #9B59FF, #6A83FF);
            border-radius: 22px;
            padding: 50px 40px;
            text-align: center;
            box-shadow: 0 0 50px rgba(155, 89, 255, 0.25);
            margin-bottom: 30px;
            overflow: hidden;
        }}

        .header-logo {{
            width: 100px;
            height: 100px;
            margin: 0 auto 20px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 0 12px rgba(155, 89, 255, 0.3);
        }}

        .header-logo-text {{
            width: 100px;
            height: 100px;
            margin: 0 auto 20px;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 42px;
            font-weight: bold;
            border: 3px solid rgba(255, 255, 255, 0.3);
        }}

        .header-title {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
            text-shadow: 0 0 6px rgba(155, 89, 255, 0.55);
        }}

        .header-subtitle {{
            font-size: 16px;
            opacity: 0.9;
        }}

        /* Ticket Badge */
        .ticket-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            margin-top: 15px;
            text-shadow: 0 0 6px rgba(155, 89, 255, 0.55);
        }}

        /* Right Sidebar */
        .sidebar {{
            width: 350px;
            flex-shrink: 0;
        }}

        .sidebar-card {{
            background: rgba(30, 20, 50, 0.55);
            border-left: 3px solid transparent;
            border-image: linear-gradient(to bottom, #9B59FF, #6A83FF) 1;
            border-radius: 14px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }}

        .sidebar-title {{
            font-size: 16px;
            font-weight: 600;
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
        }}

        .metadata-item {{
            display: flex;
            flex-direction: column;
            gap: 5px;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(155, 89, 255, 0.18);
        }}

        .metadata-item:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}

        .metadata-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(191, 191, 220, 0.7);
            font-weight: 600;
        }}

        .metadata-value {{
            font-size: 14px;
            color: #ffffff;
            font-weight: 500;
        }}

        /* Messages Area */
        .messages-section {{
            background: rgba(20, 20, 35, 0.4);
            border-radius: 16px;
            padding: 20px;
        }}

        .message-block {{
            transition: 0.25s ease;
        }}

        .message-divider {{
            height: 1px;
            background: rgba(155, 89, 255, 0.18);
            margin: 12px 0;
        }}

        .message-container {{
            display: flex;
            gap: 15px;
            padding: 15px;
            border-radius: 12px;
            transition: 0.25s ease;
            border: 1px solid rgba(155, 89, 255, 0.25);
            background: rgba(30, 20, 50, 0.3);
        }}

        .message-container:hover {{
            transform: scale(1.02);
            box-shadow: 0 0 12px rgba(106, 131, 255, 0.35);
            border-color: rgba(155, 89, 255, 0.5);
        }}

        .avatar-container {{
            flex-shrink: 0;
        }}

        .avatar-badge {{
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: 2px solid transparent;
            border-image: linear-gradient(135deg, #9B59FF, #6A83FF) 1;
            box-shadow: 0 0 12px rgba(155, 89, 255, 0.3);
            transition: 0.25s ease;
        }}

        .avatar-badge:hover {{
            transform: scale(1.1);
            box-shadow: 0 0 16px rgba(155, 89, 255, 0.5);
        }}

        .message-body {{
            flex: 1;
            min-width: 0;
        }}

        .message-header-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}

        .author-info {{
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            padding: 6px 12px;
            border-radius: 8px;
            transition: 0.25s ease;
        }}

        .author-info:hover {{
            background: linear-gradient(135deg, rgba(155, 89, 255, 0.15), rgba(106, 131, 255, 0.15));
            box-shadow: 0 0 8px rgba(155, 89, 255, 0.2);
        }}

        .author-name {{
            font-weight: 600;
            font-size: 16px;
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .timestamp-text {{
            font-size: 12px;
            color: #bfbfdc;
        }}

        .collapse-btn {{
            background: transparent;
            border: 1px solid rgba(155, 89, 255, 0.3);
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            padding: 6px 8px;
            border-radius: 6px;
            transition: 0.25s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .collapse-btn:hover {{
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            border-color: transparent;
            color: #ffffff;
            box-shadow: 0 0 8px rgba(155, 89, 255, 0.4);
        }}

        /* User Dropdown */
        .user-dropdown {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            margin-bottom: 0;
        }}

        .user-dropdown.active {{
            max-height: 300px;
            margin-bottom: 12px;
        }}

        .user-dropdown-grid {{
            background: linear-gradient(135deg, rgba(155, 89, 255, 0.1), rgba(106, 131, 255, 0.1));
            border-radius: 10px;
            padding: 15px;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            border: 1px solid rgba(155, 89, 255, 0.3);
            box-shadow: 0 0 20px rgba(155, 89, 255, 0.35);
        }}

        .dropdown-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .dropdown-label {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: rgba(191, 191, 220, 0.7);
            font-weight: 600;
        }}

        .dropdown-value {{
            font-size: 12px;
            color: #9B59FF;
            font-family: 'Courier New', monospace;
        }}

        /* Message Content */
        .message-content-area {{
            color: rgba(255, 255, 255, 0.9);
            word-break: break-word;
            font-size: 15px;
            line-height: 1.7;
            transition: 0.25s ease;
        }}

        .message-content-area.collapsed {{
            max-height: 0;
            overflow: hidden;
            opacity: 0;
        }}

        .message-content-area strong {{
            color: #ffffff;
            font-weight: 600;
        }}

        .message-content-area em {{
            font-style: italic;
        }}

        .message-content-area u {{
            text-decoration: underline;
        }}

        .message-content-area del {{
            text-decoration: line-through;
            opacity: 0.7;
        }}

        .message-content-area code {{
            background: rgba(0, 0, 0, 0.4);
            padding: 3px 7px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            border: 1px solid rgba(155, 89, 255, 0.2);
        }}

        .mention {{
            background: rgba(155, 89, 255, 0.2);
            color: #9B59FF;
            padding: 3px 8px;
            border-radius: 5px;
            font-weight: 600;
            border: 1px solid rgba(155, 89, 255, 0.3);
        }}

        .no-content {{
            opacity: 0.5;
            font-style: italic;
            color: #bfbfdc;
        }}

        .embed-content {{
            background: rgba(155, 89, 255, 0.08);
            border-left: 3px solid #9B59FF;
            padding: 15px;
            margin-top: 12px;
            border-radius: 8px;
            font-size: 14px;
        }}

        .attachment-item {{
            margin-top: 12px;
            padding: 12px;
            background: rgba(30, 20, 50, 0.5);
            border-radius: 10px;
            border: 1px solid rgba(155, 89, 255, 0.25);
        }}

        .attachment-item img {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            margin-top: 8px;
        }}

        .attachment-item a {{
            color: #9B59FF;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: 0.25s ease;
        }}

        .attachment-item a:hover {{
            color: #6A83FF;
            text-shadow: 0 0 8px rgba(155, 89, 255, 0.4);
        }}

        /* Footer */
        .footer-section {{
            text-align: center;
            padding: 40px 25px;
            margin-top: 30px;
            background: rgba(20, 10, 30, 0.4);
            border-radius: 16px;
        }}

        .footer-logo-text {{
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(135deg, #9B59FF, #6A83FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 12px;
        }}

        .footer-text {{
            font-size: 13px;
            color: rgba(191, 191, 220, 0.7);
            margin-bottom: 8px;
        }}

        .footer-link {{
            color: #9B59FF;
            text-decoration: none;
            font-weight: 500;
            transition: 0.25s ease;
        }}

        .footer-link:hover {{
            color: #6A83FF;
            text-shadow: 0 0 8px rgba(155, 89, 255, 0.4);
        }}

        /* Responsive */
        @media (max-width: 1200px) {{
            .main-layout {{
                flex-direction: column;
            }}

            .sidebar {{
                width: 100%;
            }}

            .user-dropdown-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 768px) {{
            .top-nav {{
                flex-direction: column;
                gap: 15px;
            }}

            .search-container {{
                max-width: 100%;
            }}

            .message-container {{
                flex-direction: column;
            }}

            .message-content-area {{
                padding-left: 0;
            }}
        }}
    </style>
</head>
<body>
    <!-- Sticky Navigation -->
    <div class="top-nav">
        <div class="nav-title">{document_type} #{ticket_number}</div>
        <div class="search-container">
            <input type="text" class="search-bar" id="searchInput" placeholder="Search messages..." oninput="searchMessages()">
        </div>
    </div>

    <!-- Main Layout -->
    <div class="main-layout">
        <!-- Content Area -->
        <div class="content-area">
            <!-- Header -->
            <div class="header-section">
                {logo_html}
                <div class="header-title">{document_type} #{ticket_number}</div>
                <div class="header-subtitle">Official Transcript</div>
                <div class="ticket-badge">{ticket_type_display}</div>
            </div>

            <!-- Messages -->
            <div class="messages-section" id="messagesContainer">
                {messages_html}
            </div>

            <!-- Footer -->
            <div class="footer-section">
                <div class="footer-logo-text">AFROO EXCHANGE</div>
                <p class="footer-text">Professional Cryptocurrency Exchange Services</p>
                <p class="footer-text"><a href="https://afrooexch.com" target="_blank" class="footer-link">AfrooExch.com</a></p>
                <p class="footer-text" style="font-size: 11px; margin-top: 10px;">Generated on {datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")}</p>
            </div>
        </div>

        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-card">
                <div class="sidebar-title">Ticket Information</div>
                <div class="metadata-item">
                    <span class="metadata-label">Ticket Type</span>
                    <span class="metadata-value">{ticket_type_display}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Status</span>
                    <span class="metadata-value">Resolved</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Total Messages</span>
                    <span class="metadata-value">{msg_count}</span>
                </div>
            </div>

            <div class="sidebar-card">
                <div class="sidebar-title">Timeline</div>
                <div class="metadata-item">
                    <span class="metadata-label">Opened By</span>
                    <span class="metadata-value">{opened_by.name}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Opened At</span>
                    <span class="metadata-value">{opened_at.strftime("%B %d, %Y")}</span>
                    <span class="metadata-value" style="font-size: 12px; opacity: 0.7;">{opened_at.strftime("%I:%M %p UTC")}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Closed By</span>
                    <span class="metadata-value">{closed_by.name}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Closed At</span>
                    <span class="metadata-value">{closed_at.strftime("%B %d, %Y")}</span>
                    <span class="metadata-value" style="font-size: 12px; opacity: 0.7;">{closed_at.strftime("%I:%M %p UTC")}</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Toggle user info dropdown
        function toggleUserInfo(element) {{
            const dropdown = element.closest('.message-body').querySelector('.user-dropdown');
            const allDropdowns = document.querySelectorAll('.user-dropdown');

            // Close all other dropdowns
            allDropdowns.forEach(div => {{
                if (div !== dropdown) {{
                    div.classList.remove('active');
                }}
            }});

            // Toggle current
            dropdown.classList.toggle('active');
        }}

        // Toggle message collapse
        function toggleMessage(button) {{
            const messageContent = button.closest('.message-body').querySelector('.message-content-area');
            const svg = button.querySelector('svg');

            messageContent.classList.toggle('collapsed');

            // Rotate arrow
            if (messageContent.classList.contains('collapsed')) {{
                svg.style.transform = 'rotate(-90deg)';
            }} else {{
                svg.style.transform = 'rotate(0deg)';
            }}
        }}

        // Search messages
        function searchMessages() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const messages = document.querySelectorAll('.message-block');

            messages.forEach(msg => {{
                const content = msg.getAttribute('data-search-content');
                if (content.includes(searchTerm)) {{
                    msg.style.display = 'block';
                }} else {{
                    msg.style.display = 'none';
                }}
            }});
        }}

        // Smooth scroll to top on nav click
        document.querySelector('.nav-title').addEventListener('click', () => {{
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }});
    </script>
</body>
</html>'''

    return html
