"""
AI Service - OpenAI-powered smart assistant
Provides FAQ answers, calculations, ticket assistance, and platform guidance
"""

from typing import Optional, Dict, List
import logging
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered features using OpenAI"""

    # System prompt for Afroo Exchange AI Assistant
    SYSTEM_PROMPT = """You are the Afroo Exchange AI Assistant, a helpful guide for users of a cryptocurrency exchange platform.

Your responsibilities:
- Answer questions about Afroo Exchange features (wallets, swaps, exchanges, tickets)
- Provide guidance on crypto operations and best practices
- Help with exchange calculations and fee breakdowns
- Explain platform features clearly and concisely
- Assist with troubleshooting common issues

Important guidelines:
- NEVER give financial advice or investment recommendations
- NEVER make decisions for users - only provide information
- Remind users to verify critical matters with official support
- Keep all responses under 1900 characters for Discord compatibility
- Be friendly, professional, and security-conscious
- If asked about something outside your knowledge, direct users to support

Platform features you should know:
- P2P Exchange System: Users create exchange offers, exchangers claim and fulfill them
- Afroo Wallets: Custodial wallets for storing crypto on platform
- Afroo Swaps: Instant crypto-to-crypto exchanges via ChangeNow
- Support Tickets: Help system for users
- Exchanger Deposits: Deposit wallets with hold/escrow system
- Fee Structure: 2% platform fee or $0.50 minimum, 0.5% swap fee

Always remind users about security:
- Never share private keys
- Verify addresses before sending
- Use 2FA when available
- Be cautious of scams
"""

    def __init__(self):
        """Initialize OpenAI client"""
        if settings.FEATURE_AI_ENABLED and settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
            self.max_tokens = settings.OPENAI_MAX_TOKENS
            self.temperature = settings.OPENAI_TEMPERATURE
            self.enabled = True
            logger.info(f"AI Service initialized with model: {self.model}")
        else:
            self.enabled = False
            logger.warning("AI Service disabled - check FEATURE_AI_ENABLED and OPENAI_API_KEY")

    async def answer_question(
        self,
        question: str,
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Answer user questions using AI.

        Args:
            question: User's question
            context: Optional context (user info, platform stats, etc.)
            conversation_history: Previous messages in conversation

        Returns:
            Dict with answer and metadata
        """
        try:
            if not self.enabled:
                return {
                    "answer": "AI assistant is currently unavailable. Please contact support for assistance.",
                    "success": False,
                    "error": "AI service disabled"
                }

            # Build messages
            messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history[-5:])  # Last 5 messages for context

            # Add context if provided
            if context:
                context_str = f"\nCurrent context: {self._format_context(context)}"
                messages.append({"role": "system", "content": context_str})

            # Add user question
            messages.append({"role": "user", "content": question})

            # Call OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            answer = response.choices[0].message.content

            # Ensure answer isn't too long for Discord
            if len(answer) > 1900:
                answer = answer[:1897] + "..."

            logger.info(f"AI answered question: {question[:50]}...")

            return {
                "answer": answer,
                "success": True,
                "tokens_used": response.usage.total_tokens,
                "model": self.model
            }

        except Exception as e:
            logger.error(f"AI service error: {e}", exc_info=True)
            return {
                "answer": "I encountered an error processing your question. Please try again or contact support.",
                "success": False,
                "error": str(e)
            }

    async def calculate_exchange(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate: float,
        include_fees: bool = True
    ) -> Dict:
        """
        Calculate exchange with fee breakdown.

        Args:
            amount: Amount to exchange
            from_currency: Source currency
            to_currency: Destination currency
            rate: Exchange rate
            include_fees: Whether to include platform fees

        Returns:
            Dict with calculation breakdown
        """
        try:
            # Calculate base exchange
            output_amount = amount * rate

            # Calculate fees
            platform_fee = 0.0
            swap_fee = 0.0

            if include_fees:
                # Platform fee: 2% or $0.50 minimum
                platform_fee_percent = amount * 0.02
                platform_fee = max(platform_fee_percent, 0.50)

                # Swap fee: 0.5%
                swap_fee = amount * 0.005

            total_deducted = amount + platform_fee + swap_fee
            net_output = output_amount

            return {
                "input_amount": amount,
                "input_currency": from_currency,
                "output_amount": net_output,
                "output_currency": to_currency,
                "exchange_rate": rate,
                "platform_fee": platform_fee,
                "swap_fee": swap_fee,
                "total_fee": platform_fee + swap_fee,
                "total_deducted": total_deducted,
                "breakdown": (
                    f"**Exchange Calculation**\n"
                    f"Input: {amount} {from_currency}\n"
                    f"Rate: 1 {from_currency} = {rate} {to_currency}\n"
                    f"Output (before fees): {output_amount:.8f} {to_currency}\n\n"
                    f"**Fees:**\n"
                    f"Platform Fee (2%): {platform_fee:.2f} USD\n"
                    f"Swap Fee (0.5%): {swap_fee:.8f} {from_currency}\n"
                    f"Total Fees: {platform_fee + swap_fee:.2f} USD\n\n"
                    f"**Final:**\n"
                    f"You send: {total_deducted:.8f} {from_currency}\n"
                    f"You receive: {net_output:.8f} {to_currency}"
                )
            }

        except Exception as e:
            logger.error(f"Exchange calculation error: {e}")
            return {"error": str(e)}

    async def suggest_ticket_response(
        self,
        ticket_subject: str,
        ticket_description: str,
        conversation_history: List[Dict]
    ) -> Dict:
        """
        Suggest response for support tickets (for staff).

        Args:
            ticket_subject: Ticket subject
            ticket_description: Initial ticket description
            conversation_history: Previous messages in ticket

        Returns:
            Dict with suggested response
        """
        try:
            if not self.enabled:
                return {"suggestion": None, "success": False}

            prompt = f"""As a support staff member, suggest a helpful response to this ticket.

Subject: {ticket_subject}
Description: {ticket_description}

Previous conversation:
{self._format_conversation(conversation_history)}

Suggest a professional, helpful response that:
1. Addresses the user's concern
2. Provides clear next steps
3. Is empathetic and professional
4. Includes any relevant warnings or security tips

Keep it under 500 characters."""

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )

            suggestion = response.choices[0].message.content

            return {
                "suggestion": suggestion,
                "success": True,
                "note": "This is an AI suggestion - please review before sending"
            }

        except Exception as e:
            logger.error(f"Ticket response suggestion error: {e}")
            return {"suggestion": None, "success": False, "error": str(e)}

    async def generate_faq_answer(self, category: str, question: str) -> Dict:
        """
        Generate FAQ answer for common questions.

        Args:
            category: FAQ category (wallet, exchange, security, etc.)
            question: The FAQ question

        Returns:
            Dict with generated answer
        """
        try:
            if not self.enabled:
                return {"answer": None, "success": False}

            prompt = f"""Generate a clear, concise FAQ answer for this question in the {category} category:

Question: {question}

Requirements:
- Clear and easy to understand
- Include step-by-step instructions if applicable
- Mention any important warnings or security tips
- Keep under 300 words
- Format for readability (use bullet points where appropriate)"""

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=400,
                temperature=0.5
            )

            answer = response.choices[0].message.content

            return {
                "question": question,
                "category": category,
                "answer": answer,
                "success": True
            }

        except Exception as e:
            logger.error(f"FAQ generation error: {e}")
            return {"answer": None, "success": False, "error": str(e)}

    def _format_context(self, context: Dict) -> str:
        """Format context dict into readable string"""
        parts = []
        for key, value in context.items():
            parts.append(f"{key}: {value}")
        return ", ".join(parts)

    def _format_conversation(self, history: List[Dict]) -> str:
        """Format conversation history"""
        if not history:
            return "No previous messages"

        formatted = []
        for msg in history[-5:]:  # Last 5 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"{role.title()}: {content}")

        return "\n".join(formatted)

    async def health_check(self) -> Dict:
        """Check if AI service is healthy"""
        try:
            if not self.enabled:
                return {
                    "healthy": False,
                    "reason": "AI service disabled"
                }

            # Simple test query
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Test"}
                ],
                max_tokens=10
            )

            return {
                "healthy": True,
                "model": self.model,
                "test_successful": True
            }

        except Exception as e:
            logger.error(f"AI health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }


# Create global AI service instance
ai_service = AIService()


# Convenience functions
async def ask_ai(question: str, context: Optional[Dict] = None) -> str:
    """Quick helper to ask AI a question"""
    result = await ai_service.answer_question(question, context)
    return result.get("answer", "AI assistant unavailable")


async def calculate_exchange_ai(amount: float, from_curr: str, to_curr: str, rate: float) -> Dict:
    """Quick helper for exchange calculations"""
    return await ai_service.calculate_exchange(amount, from_curr, to_curr, rate)
