import time

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.core.kv import get_kv

from app.api.v1.deps import DbSession, CurrentUser
from app.schemas import ChatRequest, ChatResponse, MessageResponse
from app.ai.shopping_agent import ShoppingAgent

router = APIRouter(prefix="/chat", tags=["AI Chat"])


async def _hit(key: str, limit: int, window_seconds: int) -> bool:
    """Count one request in a fixed window; return False once the limit is exceeded."""
    if limit <= 0:
        return True
    kv = get_kv(decode_responses=True)
    bucket = f"{key}:{int(time.time() // window_seconds)}"
    count = int(await kv.get(bucket) or 0) + 1
    await kv.setex(bucket, window_seconds, str(count))
    return count <= limit


async def enforce_chat_limits(user_id) -> None:
    """Per-user and app-wide caps so a public demo cannot exhaust the LLM quota."""
    if not await _hit(f"ratelimit:chat:user:{user_id}", settings.chat_rate_limit_per_hour, 3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've reached the hourly chat limit for this demo. Please try again later.",
        )
    if not await _hit("ratelimit:chat:global", settings.chat_daily_limit, 86400):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The demo assistant has reached its daily limit. Please come back tomorrow.",
        )


@router.post("", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Send a message to the AI shopping assistant.
    
    The assistant can:
    - Search for products
    - Add items to your cart
    - Get personalized recommendations
    - Answer policy questions
    - Check order status
    """
    await enforce_chat_limits(current_user.id)
    agent = ShoppingAgent(db, current_user.id)
    result = await agent.chat(request.message)
    
    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls"),
        error=result.get("error"),
    )


@router.delete("/history", response_model=MessageResponse)
async def clear_chat_history(
    db: DbSession,
    current_user: CurrentUser,
):
    """Clear conversation history with the AI assistant."""
    agent = ShoppingAgent(db, current_user.id)
    await agent.clear_conversation()
    
    return MessageResponse(message="Conversation history cleared")
