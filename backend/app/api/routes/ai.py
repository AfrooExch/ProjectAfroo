"""
AI Assistant Routes - OpenAI-powered smart assistant endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.api.dependencies import get_current_user, require_staff
# Temporarily disabled AI service due to library incompatibility
# from app.services.ai_service import ai_service
ai_service = None  # Placeholder

router = APIRouter()


class AskQuestionRequest(BaseModel):
    """Request to ask AI a question"""
    question: str
    context: Optional[Dict] = None
    conversation_history: Optional[List[Dict]] = None


class CalculateExchangeRequest(BaseModel):
    """Request for exchange calculation"""
    amount: float
    from_currency: str
    to_currency: str
    rate: float
    include_fees: bool = True


class TicketSuggestionRequest(BaseModel):
    """Request for ticket response suggestion"""
    ticket_subject: str
    ticket_description: str
    conversation_history: List[Dict]


class FAQGenerateRequest(BaseModel):
    """Request to generate FAQ answer"""
    category: str
    question: str


@router.post("/ai/ask")
async def ask_ai_question(
    request: AskQuestionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Ask AI assistant a question"""
    try:
        result = await ai_service.answer_question(
            question=request.question,
            context=request.context,
            conversation_history=request.conversation_history
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.get("error", "AI service unavailable")
            )

        return {
            "success": True,
            "answer": result["answer"],
            "tokens_used": result.get("tokens_used"),
            "model": result.get("model")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/ai/calculate")
async def calculate_exchange(
    request: CalculateExchangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Calculate exchange with AI-formatted breakdown"""
    try:
        result = await ai_service.calculate_exchange(
            amount=request.amount,
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            rate=request.rate,
            include_fees=request.include_fees
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        return {
            "success": True,
            "calculation": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/ai/ticket/suggest", dependencies=[Depends(require_staff)])
async def suggest_ticket_response(
    request: TicketSuggestionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Suggest response for support ticket (staff only).
    Helps staff respond faster with AI suggestions.
    """
    try:
        result = await ai_service.suggest_ticket_response(
            ticket_subject=request.ticket_subject,
            ticket_description=request.ticket_description,
            conversation_history=request.conversation_history
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI suggestion unavailable"
            )

        return {
            "success": True,
            "suggestion": result["suggestion"],
            "note": result.get("note")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/ai/faq/generate", dependencies=[Depends(require_staff)])
async def generate_faq_answer(
    request: FAQGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate FAQ answer using AI (staff only).
    Helps staff create comprehensive FAQ entries.
    """
    try:
        result = await ai_service.generate_faq_answer(
            category=request.category,
            question=request.question
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FAQ generation unavailable"
            )

        return {
            "success": True,
            "faq": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/ai/health")
async def ai_health_check():
    """Check AI service health (public)"""
    try:
        health = await ai_service.health_check()

        status_code = status.HTTP_200_OK if health.get("healthy") else status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "success": health.get("healthy", False),
            **health
        }

    except Exception as e:
        return {
            "success": False,
            "healthy": False,
            "error": str(e)
        }
