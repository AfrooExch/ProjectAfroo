"""
Transcript Service - Generates ticket transcripts for history
Creates HTML transcripts of ticket exchanges
"""

from typing import List, Dict, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_tickets_collection, get_users_collection

logger = logging.getLogger(__name__)


class TranscriptService:
    """Service for generating ticket transcripts"""

    @staticmethod
    async def generate_transcript(ticket_id: str) -> Dict:
        """
        Generate a transcript for a completed ticket
        Returns dict with HTML and text versions
        """
        tickets = get_tickets_collection()
        users = get_users_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Get client and exchanger info
        client_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
        exchanger_id = ticket.get("assigned_to")

        # Get messages
        messages = ticket.get("messages", [])

        # Build transcript data
        transcript_data = {
            "ticket_number": ticket.get("ticket_number", "Unknown"),
            "client_discord_id": client_discord_id,
            "exchanger_id": str(exchanger_id) if exchanger_id else "Unknown",
            "amount_usd": ticket.get("amount_usd", 0),
            "receiving_amount": ticket.get("receiving_amount", 0),
            "fee_amount": ticket.get("fee_amount", 0),
            "send_method": ticket.get("send_method", "Unknown"),
            "receive_method": ticket.get("receive_method", "Unknown"),
            "created_at": ticket.get("created_at"),
            "closed_at": ticket.get("closed_at"),
            "payout_type": ticket.get("payout_type", "Unknown"),
            "messages": messages,
            "status": ticket.get("status", "Unknown")
        }

        # Generate HTML transcript
        html_transcript = TranscriptService._generate_html_transcript(transcript_data)

        # Generate text transcript
        text_transcript = TranscriptService._generate_text_transcript(transcript_data)

        return {
            "ticket_id": ticket_id,
            "ticket_number": transcript_data["ticket_number"],
            "html": html_transcript,
            "text": text_transcript,
            "generated_at": datetime.utcnow()
        }

    @staticmethod
    def _generate_html_transcript(data: Dict) -> str:
        """Generate HTML version of transcript with purple gradient theme"""

        # Format dates
        created = data["created_at"].strftime("%B %d, %Y at %I:%M %p") if data["created_at"] else "Unknown"
        closed = data["closed_at"].strftime("%B %d, %Y at %I:%M %p") if data["closed_at"] else "In Progress"

        # Calculate duration
        duration = "Unknown"
        if data["created_at"] and data["closed_at"]:
            delta = data["closed_at"] - data["created_at"]
            minutes = delta.total_seconds() / 60
            if minutes < 60:
                duration = f"{int(minutes)} minutes"
            else:
                hours = int(minutes / 60)
                mins = int(minutes % 60)
                duration = f"{hours}h {mins}m"

        # Build message log
        message_html = ""
        for msg in data["messages"]:
            timestamp = msg.get("created_at", datetime.utcnow()).strftime("%I:%M %p") if msg.get("created_at") else "Unknown"
            sender = msg.get("sender_name", "System")
            content = msg.get("message", msg.get("content", ""))
            is_internal = msg.get("is_internal", False)

            # Determine message type
            msg_class = "system" if is_internal else "message"

            message_html += f"""
            <div class="{msg_class}">
                <div class="message-header">
                    <span class="message-author">{sender}</span>
                    <span class="message-time">{timestamp}</span>
                </div>
                <div class="message-content">{content}</div>
            </div>
            """

        # Calculate profit for display
        platform_fee = data.get("fee_amount", 0)
        amount_usd = data.get("amount_usd", 0)
        server_fee = max(0.50, amount_usd * 0.02)
        exchanger_profit = platform_fee - server_fee

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket #{data['ticket_number']} Transcript - Afroo Exchange</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            padding: 50px 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 900px;
            background: white;
            margin: 0 auto;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .header {{
            background: #9E6BFF;
            color: white;
            padding: 40px;
        }}

        .header h1 {{
            font-size: 28px;
            margin-bottom: 20px;
        }}

        .header-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}

        .header-info-item {{
            background: rgba(255, 255, 255, 0.1);
            padding: 12px;
            border-radius: 8px;
        }}

        .header-info-label {{
            font-size: 12px;
            opacity: 0.8;
            margin-bottom: 5px;
        }}

        .header-info-value {{
            font-size: 16px;
            font-weight: 600;
        }}

        .messages {{
            padding: 30px;
        }}

        .message {{
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 4px solid #ddd;
            background: #f5f5f5;
        }}

        .message-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }}

        .message-author {{
            font-weight: 600;
            color: #333;
        }}

        .message-time {{
            font-size: 13px;
            color: #666;
        }}

        .message-content {{
            color: #444;
            line-height: 1.6;
        }}

        .system {{
            background: #f0f0f0;
            border-left-color: #999;
            font-style: italic;
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 8px;
        }}

        .footer {{
            background: #f8f9fa;
            padding: 30px;
            border-top: 1px solid #dee2e6;
        }}

        .footer h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #333;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}

        .stat-item {{
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }}

        .stat-label {{
            font-size: 13px;
            color: #666;
            margin-bottom: 5px;
        }}

        .stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: #9E6BFF;
        }}

        .logo {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 14px;
        }}

        .logo a {{
            color: #9E6BFF;
            text-decoration: none;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 20px 10px;
            }}

            .header {{
                padding: 30px 20px;
            }}

            .messages {{
                padding: 20px 15px;
            }}

            .header h1 {{
                font-size: 24px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Ticket #{data['ticket_number']} Transcript</h1>
            <div class="header-info">
                <div class="header-info-item">
                    <div class="header-info-label">Exchange Type</div>
                    <div class="header-info-value">{data['send_method']} → {data['receive_method']}</div>
                </div>
                <div class="header-info-item">
                    <div class="header-info-label">Amount</div>
                    <div class="header-info-value">${data['amount_usd']:.2f}</div>
                </div>
                <div class="header-info-item">
                    <div class="header-info-label">Status</div>
                    <div class="header-info-value">{data['status'].title()}</div>
                </div>
                <div class="header-info-item">
                    <div class="header-info-label">Duration</div>
                    <div class="header-info-value">{duration}</div>
                </div>
            </div>
        </div>

        <div class="messages">
            <h2 style="margin-bottom: 20px; color: #333;">Conversation</h2>
            {message_html if message_html else '<div class="system"><div class="message-content">No messages recorded for this ticket.</div></div>'}
        </div>

        <div class="footer">
            <h2>Exchange Summary</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Platform Fee</div>
                    <div class="stat-value">${platform_fee:.2f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Server Fee</div>
                    <div class="stat-value">${server_fee:.2f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Exchanger Profit</div>
                    <div class="stat-value">${exchanger_profit:.2f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Client Received</div>
                    <div class="stat-value">${data['receiving_amount']:.2f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Created</div>
                    <div class="stat-value" style="font-size: 14px;">{created}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Completed</div>
                    <div class="stat-value" style="font-size: 14px;">{closed}</div>
                </div>
            </div>
        </div>

        <div class="logo">
            Generated by Afroo Exchange<br>
            <a href="https://afrooexchange.com">afrooexchange.com</a>
        </div>
    </div>
</body>
</html>
        """

        return html

    @staticmethod
    def _generate_text_transcript(data: Dict) -> str:
        """Generate plain text version of transcript"""

        created = data["created_at"].strftime("%Y-%m-%d %H:%M:%S UTC") if data["created_at"] else "Unknown"
        closed = data["closed_at"].strftime("%Y-%m-%d %H:%M:%S UTC") if data["closed_at"] else "Unknown"

        text = f"""
========================================
EXCHANGE TRANSCRIPT - TICKET #{data['ticket_number']}
========================================

EXCHANGE DETAILS
----------------
Client:           {data['client_discord_id']}
Exchanger:        {data['exchanger_id']}
Exchange Type:    {data['send_method']} → {data['receive_method']}
Amount:           ${data['amount_usd']:.2f} USD
Fee:              ${data['fee_amount']:.2f} USD
Client Received:  ${data['receiving_amount']:.2f} USD
Payout Method:    {data['payout_type']}
Created:          {created}
Closed:           {closed}

MESSAGE LOG
-----------
"""

        for msg in data["messages"]:
            timestamp = msg.get("timestamp", datetime.utcnow()).strftime("%H:%M:%S")
            sender = msg.get("sender_name", "Unknown")
            content = msg.get("content", "")
            text += f"[{timestamp}] {sender}: {content}\n"

        if not data["messages"]:
            text += "No messages recorded\n"

        text += """
========================================
Generated by Afroo Exchange System
========================================
"""

        return text

    @staticmethod
    def generate_vouch_template(ticket_data: Dict, for_role: str) -> str:
        """
        Generate pre-made vouch message for client or exchanger

        Args:
            ticket_data: Ticket data dict
            for_role: Either 'client' or 'exchanger'
        """
        ticket_number = ticket_data.get("ticket_number", "Unknown")
        amount = ticket_data.get("amount_usd", 0)

        if for_role == "client":
            # Vouch template for client to vouch for exchanger
            exchanger_id = ticket_data.get("assigned_to", "Unknown")
            return f"""**Vouch for Exchanger** 💜

I successfully completed exchange ticket #{ticket_number} with <@{exchanger_id}>!

**Amount:** ${amount:.2f} USD
**Status:** Completed Successfully
**Experience:** Smooth and professional exchange

Thanks for the great service! ⭐"""

        else:  # for_role == 'exchanger'
            # Vouch template for exchanger to vouch for client
            client_id = ticket_data.get("discord_user_id", ticket_data.get("user_id", "Unknown"))
            return f"""**Vouch for Client** 💜

I successfully completed exchange ticket #{ticket_number} with <@{client_id}>!

**Amount:** ${amount:.2f} USD
**Status:** Completed Successfully
**Experience:** Professional and prompt client

Thanks for the smooth transaction! ⭐"""
