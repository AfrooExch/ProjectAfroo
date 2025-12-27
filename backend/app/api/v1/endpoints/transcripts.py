"""
Transcript Endpoints
Handles uploading and serving ticket transcripts
"""

import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Response
from fastapi.responses import HTMLResponse

from app.core.database import get_db_collection
from app.core.config import settings
from app.models.transcript import (
    TranscriptMetadata,
    TranscriptUploadRequest,
    TranscriptUploadResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Base directory for transcript storage
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "../../../../../transcripts")


def get_bot_token_from_header(x_bot_token: Optional[str] = Header(None)) -> str:
    """Verify bot service token for upload endpoint"""
    if not x_bot_token:
        raise HTTPException(status_code=401, detail="Bot token required")

    # Get bot service token from environment
    expected_token = os.getenv("BOT_SERVICE_TOKEN")
    if not expected_token:
        logger.error("BOT_SERVICE_TOKEN not configured in environment")
        raise HTTPException(status_code=500, detail="Server configuration error")

    if x_bot_token != expected_token:
        logger.warning(f"Invalid bot token attempt")
        raise HTTPException(status_code=403, detail="Invalid bot token")

    return x_bot_token


@router.post("/upload", response_model=TranscriptUploadResponse)
async def upload_transcript(
    request: TranscriptUploadRequest,
    x_bot_token: str = Header(..., alias="X-Bot-Token")
):
    """
    Upload a transcript (Bot service only)

    Requires X-Bot-Token header with valid bot service token.
    Saves HTML file and stores metadata in database.
    Returns public URL for viewing.
    """
    # Verify bot token
    get_bot_token_from_header(x_bot_token)

    try:
        # Validate ticket type
        valid_types = ['ticket', 'swap', 'automm', 'application', 'support']
        if request.ticket_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ticket_type. Must be one of: {', '.join(valid_types)}"
            )

        # Create directory structure if it doesn't exist
        type_dir = os.path.join(TRANSCRIPTS_DIR, request.ticket_type)
        os.makedirs(type_dir, exist_ok=True)

        # Generate filename (sanitize ticket_id for filesystem)
        safe_ticket_id = request.ticket_id.replace('/', '_').replace('\\', '_')
        filename = f"{safe_ticket_id}.html"
        file_path = os.path.join(type_dir, filename)

        # Write HTML file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.html_content)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Store metadata in database
        transcripts_collection = await get_db_collection("transcript_metadata")

        metadata = {
            "ticket_id": request.ticket_id,
            "ticket_type": request.ticket_type,
            "ticket_number": request.ticket_number,
            "user_id": request.user_id,
            "participants": request.participants,
            "file_path": file_path,
            "file_size": file_size,
            "message_count": request.message_count,
            "generated_at": datetime.utcnow(),
            "view_count": 0,
            "last_viewed_at": None,
            "status": "active"
        }

        result = await transcripts_collection.insert_one(metadata)
        transcript_id = str(result.inserted_id)

        # Generate public URL
        base_url = os.getenv("PUBLIC_URL", "http://localhost:8001")
        public_url = f"{base_url}/transcripts/{request.ticket_type}/{safe_ticket_id}"

        logger.info(
            f"Transcript uploaded: {request.ticket_type}/{safe_ticket_id} "
            f"for user {request.user_id} ({file_size} bytes)"
        )

        return TranscriptUploadResponse(
            success=True,
            transcript_id=transcript_id,
            public_url=public_url,
            file_path=file_path,
            file_size=file_size
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading transcript: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload transcript: {str(e)}")


@router.get("/{ticket_type}/{ticket_id}", response_class=HTMLResponse)
async def view_transcript(
    ticket_type: str,
    ticket_id: str
):
    """
    View a transcript (Public access)

    Returns the HTML transcript file.
    No authentication required - anyone with the URL can view.
    """
    try:
        # Validate ticket type
        valid_types = ['ticket', 'swap', 'automm', 'application', 'support']
        if ticket_type not in valid_types:
            raise HTTPException(
                status_code=404,
                detail="Transcript not found"
            )

        # Get metadata from database
        transcripts_collection = await get_db_collection("transcript_metadata")

        # Sanitize ticket_id for consistency
        safe_ticket_id = ticket_id.replace('/', '_').replace('\\', '_')

        metadata = await transcripts_collection.find_one({
            "ticket_id": safe_ticket_id,
            "ticket_type": ticket_type,
            "status": "active"
        })

        # Also try with unsanitized ID in case it was stored differently
        if not metadata:
            metadata = await transcripts_collection.find_one({
                "ticket_id": ticket_id,
                "ticket_type": ticket_type,
                "status": "active"
            })

        if not metadata:
            raise HTTPException(status_code=404, detail="Transcript not found")

        # Read HTML file
        file_path = metadata["file_path"]

        if not os.path.exists(file_path):
            logger.error(f"Transcript file not found on disk: {file_path}")
            raise HTTPException(status_code=404, detail="Transcript file not found")

        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Update view count and last viewed timestamp
        await transcripts_collection.update_one(
            {"_id": metadata["_id"]},
            {
                "$inc": {"view_count": 1},
                "$set": {"last_viewed_at": datetime.utcnow()}
            }
        )

        logger.info(
            f"Transcript viewed: {ticket_type}/{ticket_id} "
            f"(view #{metadata.get('view_count', 0) + 1})"
        )

        # Return HTML with proper headers
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "X-Content-Type-Options": "nosniff"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving transcript: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load transcript")


@router.get("/{ticket_type}/{ticket_id}/metadata")
async def get_transcript_metadata(
    ticket_type: str,
    ticket_id: str
):
    """
    Get transcript metadata without loading the full HTML

    Public endpoint - useful for checking if transcript exists
    """
    try:
        transcripts_collection = await get_db_collection("transcript_metadata")

        safe_ticket_id = ticket_id.replace('/', '_').replace('\\', '_')

        metadata = await transcripts_collection.find_one({
            "ticket_id": safe_ticket_id,
            "ticket_type": ticket_type,
            "status": "active"
        })

        if not metadata and safe_ticket_id != ticket_id:
            metadata = await transcripts_collection.find_one({
                "ticket_id": ticket_id,
                "ticket_type": ticket_type,
                "status": "active"
            })

        if not metadata:
            raise HTTPException(status_code=404, detail="Transcript not found")

        return {
            "ticket_id": metadata["ticket_id"],
            "ticket_type": metadata["ticket_type"],
            "ticket_number": metadata.get("ticket_number"),
            "message_count": metadata.get("message_count", 0),
            "file_size": metadata["file_size"],
            "generated_at": metadata["generated_at"],
            "view_count": metadata.get("view_count", 0),
            "last_viewed_at": metadata.get("last_viewed_at")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get metadata")


@router.get("/user/{user_id}/list")
async def list_user_transcripts(
    user_id: str,
    limit: int = 20,
    skip: int = 0
):
    """
    List all transcripts for a specific user

    Public endpoint - returns metadata for all transcripts where user_id matches
    """
    try:
        transcripts_collection = await get_db_collection("transcript_metadata")

        # Find all transcripts for this user
        cursor = transcripts_collection.find({
            "user_id": user_id,
            "status": "active"
        }).sort("generated_at", -1).skip(skip).limit(limit)

        transcripts = []
        async for doc in cursor:
            # Generate public URL
            base_url = os.getenv("PUBLIC_URL", "http://localhost:8001")
            public_url = f"{base_url}/transcripts/{doc['ticket_type']}/{doc['ticket_id']}"

            transcripts.append({
                "ticket_id": doc["ticket_id"],
                "ticket_type": doc["ticket_type"],
                "ticket_number": doc.get("ticket_number"),
                "message_count": doc.get("message_count", 0),
                "file_size": doc["file_size"],
                "generated_at": doc["generated_at"],
                "view_count": doc.get("view_count", 0),
                "last_viewed_at": doc.get("last_viewed_at"),
                "public_url": public_url
            })

        # Get total count
        total_count = await transcripts_collection.count_documents({
            "user_id": user_id,
            "status": "active"
        })

        return {
            "transcripts": transcripts,
            "total": total_count,
            "limit": limit,
            "skip": skip
        }

    except Exception as e:
        logger.error(f"Error listing user transcripts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list transcripts")
