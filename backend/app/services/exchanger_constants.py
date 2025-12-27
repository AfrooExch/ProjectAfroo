"""
Exchanger Constants - Preset Questions and Configuration
"""

# ====================
# Preset Questions (13 Total)
# ====================

PRESET_QUESTIONS = [
    {
        "id": "proof_ready",
        "text": "Do you have proof of payment ready?",
        "type": "preset"
    },
    {
        "id": "payment_details",
        "text": "What payment method details will you be using?",
        "type": "preset"
    },
    {
        "id": "send_first",
        "text": "Can you send funds first or need me to send first?",
        "type": "preset"
    },
    {
        "id": "time_ready",
        "text": "Approximately how long until you're ready?",
        "type": "preset"
    },
    {
        "id": "verified_account",
        "text": "Is your payment account verified and in good standing?",
        "type": "preset"
    },
    {
        "id": "previous_experience",
        "text": "Have you completed crypto exchanges before?",
        "type": "preset"
    },
    {
        "id": "id_verification",
        "text": "Are you willing to provide ID verification if needed?",
        "type": "preset"
    },
    {
        "id": "small_test",
        "text": "Would you like to start with a small test transaction first?",
        "type": "preset"
    },
    {
        "id": "wallet_ready",
        "text": "Do you have your crypto wallet address ready?",
        "type": "preset"
    },
    {
        "id": "transaction_speed",
        "text": "How quickly do you need this transaction completed?",
        "type": "preset"
    },
    {
        "id": "additional_info",
        "text": "Is there any additional information I should know?",
        "type": "preset"
    },
    {
        "id": "alt_payment",
        "text": "Would you accept an alternative payment method?",
        "type": "alt_payment",
        "requires_input": True  # Bot will show payment method selector
    },
    {
        "id": "alt_amount",
        "text": "Would you accept an alternative amount?",
        "type": "alt_amount",
        "requires_input": True  # Bot will show amount input modal
    }
]


def get_preset_questions() -> list[dict]:
    """Get list of preset questions"""
    return PRESET_QUESTIONS


def get_question_by_id(question_id: str) -> dict:
    """Get specific preset question by ID"""
    for question in PRESET_QUESTIONS:
        if question["id"] == question_id:
            return question
    return None


def format_question_text(question_id: str, alt_payment: str = None, alt_amount: str = None) -> str:
    """Format question text with alternatives"""
    question = get_question_by_id(question_id)
    if not question:
        return ""

    text = question["text"]

    # Add alternative payment method if provided
    if question["type"] == "alt_payment" and alt_payment:
        text += f"\n\n**Alternative Payment Method:** {alt_payment}"

    # Add alternative amount if provided
    if question["type"] == "alt_amount" and alt_amount:
        text += f"\n\n**Alternative Amount:** ${alt_amount} USD"

    return text
