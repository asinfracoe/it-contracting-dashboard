"""
Chat and BOM creation API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import json

from db import get_cosmos_client, ChatSession, ChatMessage, SessionContext
from config import get_settings

router = APIRouter(prefix="/api/bom", tags=["chat"])
settings = get_settings()


def _get_azure_openai_client():
    """Lazy-import and construct Azure OpenAI client."""
    try:
        from openai import AzureOpenAI
        return AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    except Exception:
        return None


# Request/Response Models
class StartSessionRequest(BaseModel):
    category: str
    user_id: Optional[str] = "demo_user"


class StartSessionResponse(BaseModel):
    session_id: str
    category: str
    message: str


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str


class ChatMessageResponse(BaseModel):
    session_id: str
    response: str
    partial_bom: Optional[Dict[str, Any]] = None
    progress: int
    complete: bool


class SessionResponse(BaseModel):
    session: ChatSession


@router.post("/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """
    Start a new BOM creation session for a specific category
    """
    try:
        cosmos_client = get_cosmos_client()
        
        # Generate session ID
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        # Create session context
        context = SessionContext(
            category=request.category,
            requirements={},
            progress=0
        )
        
        # Create initial welcome message
        welcome_message = ChatMessage(
            role="assistant",
            content=f"Great! Let's create a {request.category} BOM. I'll ask you 5 questions to generate a complete Bill of Materials. Ready to start?",
            timestamp=datetime.utcnow()
        )
        
        # Create session
        session = ChatSession(
            session_id=session_id,
            user_id=request.user_id,
            category=request.category,
            messages=[welcome_message],
            context=context,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status="active"
        )
        
        # Save to database
        cosmos_client.create_session(session.model_dump())
        
        return StartSessionResponse(
            session_id=session_id,
            category=request.category,
            message=welcome_message.content
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.post("/chat", response_model=ChatMessageResponse)
async def send_message(request: ChatMessageRequest):
    """
    Send a message in an active BOM creation session
    """
    try:
        cosmos_client = get_cosmos_client()
        
        # Get session
        session_data = cosmos_client.get_session(request.session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        session = ChatSession(**session_data)
        
        # Add user message
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        session.messages.append(user_message)
        
        # TODO: Call AI agent to process message and generate response
        # For now, use simple response logic
        response_text, partial_bom, progress, complete = await process_chat_message(
            session, request.message
        )
        
        # Add assistant message
        assistant_message = ChatMessage(
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow()
        )
        session.messages.append(assistant_message)
        
        # Update session
        session.context.progress = progress
        session.updated_at = datetime.utcnow()
        if complete:
            session.status = "completed"
        
        cosmos_client.update_session(
            request.session_id,
            session.model_dump()
        )
        
        return ChatMessageResponse(
            session_id=request.session_id,
            response=response_text,
            partial_bom=partial_bom,
            progress=progress,
            complete=complete
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """
    Get session details and history
    """
    try:
        cosmos_client = get_cosmos_client()
        
        session_data = cosmos_client.get_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return SessionResponse(session=ChatSession(**session_data))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


# Helper function - AI agent orchestration
async def process_chat_message(
    session: ChatSession,
    message: str
) -> tuple[str, Optional[Dict], int, bool]:
    """
    Process chat message via Azure OpenAI if configured, else fallback to rule-based flow.
    """
    if settings.use_azure_openai and settings.azure_openai_endpoint != "https://dummy.openai.azure.com/":
        return await _process_with_azure_openai(session, message)
    return await _process_rule_based(session, message)


async def _process_with_azure_openai(
    session: ChatSession,
    message: str
) -> tuple[str, Optional[Dict], int, bool]:
    """Call Azure OpenAI to generate BOM assistant response."""
    client = _get_azure_openai_client()
    if not client:
        return await _process_rule_based(session, message)

    system_prompt = (
        "You are an IT procurement BOM (Bill of Materials) assistant. "
        "Help the user create detailed BOMs for IT infrastructure projects. "
        "Ask up to 5 targeted questions about: scale (units/sites/users), redundancy needs, "
        "storage/capacity, DR/backup requirements, and preferred vendors. "
        "Once you have enough information, generate a JSON BOM with line_items (each having: "
        "line_number, description, qty, unit_price, extended_price, category). "
        "When generating the BOM, wrap it in ```json ... ``` fences and follow it with a summary. "
        f"The current project category is: {session.category}."
    )

    messages_payload = [{"role": "system", "content": system_prompt}]
    for m in session.messages[-10:]:  # last 10 to stay within context
        messages_payload.append({"role": m.role, "content": m.content})
    messages_payload.append({"role": "user", "content": message})

    try:
        completion = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=messages_payload,
            max_tokens=settings.azure_openai_max_tokens,
            temperature=settings.azure_openai_temperature,
        )
        response_text = completion.choices[0].message.content or ""
    except Exception as e:
        # Graceful fallback on API error
        return await _process_rule_based(session, message)

    # Extract JSON BOM if present in response
    partial_bom = None
    complete = False
    if "```json" in response_text:
        try:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(json_str)
            if "line_items" in parsed:
                partial_bom = parsed
                complete = True
        except Exception:
            pass

    # Estimate progress from conversation length
    progress = min(90, len([m for m in session.messages if m.role == "user"]) * 18)
    if complete:
        progress = 100

    return response_text, partial_bom, progress, complete


async def _process_rule_based(
    session: ChatSession,
    message: str
) -> tuple[str, Optional[Dict], int, bool]:
    """Simple rule-based fallback when Azure OpenAI is unavailable."""
    questions_asked = len([
        m for m in session.messages
        if m.role == "assistant" and "Question" in m.content
    ])

    questions = [
        "Question 1/5: How many units do you need? (e.g., servers, sites, users)",
        "Question 2/5: Do you need high availability (HA pair)?",
        "Question 3/5: What's your storage capacity requirement? (in TB)",
        "Question 4/5: Do you need backup/disaster recovery?",
        "Question 5/5: What's your preferred vendor? (CDW, Entity, or Direct)",
    ]

    if questions_asked < len(questions):
        progress = int((questions_asked + 1) / len(questions) * 100)
        return questions[questions_asked], None, progress, False

    dummy_bom = {
        "line_items": [
            {"line_number": 1, "description": "Dell PowerEdge R750 Server", "qty": 10, "unit_price": 18500, "extended_price": 185000, "category": "Compute"},
            {"line_number": 2, "description": "VMware vSphere Enterprise Plus", "qty": 20, "unit_price": 4995, "extended_price": 99900, "category": "Software"},
            {"line_number": 3, "description": "Dell ProSupport 5Y 24x7", "qty": 10, "unit_price": 3200, "extended_price": 32000, "category": "Services"},
        ],
        "totals": {"hardware": 185000, "software": 99900, "services": 32000, "total_otc": 316900},
    }
    return (
        "BOM generated successfully! You can review it in the preview panel. "
        "Would you like to export it or make any adjustments?",
        dummy_bom, 100, True
    )
