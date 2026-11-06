from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# --- Chat Schemas ---

class ChatMessage(BaseModel):
    """Single chat message."""
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """Schema for chat request."""
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    """Schema for chat response."""
    response: str
    tool_calls: Optional[List[dict]] = None


# --- Recommendation Schemas ---

class RecommendationResponse(BaseModel):
    """Schema for product recommendation."""
    id: UUID
    name: str
    slug: str
    price: float
    image_url: Optional[str]
    avg_rating: float
    score: float  # Recommendation confidence score


class RecommendationsListResponse(BaseModel):
    """Schema for recommendations list."""
    recommendations: List[RecommendationResponse]
    based_on: str  # e.g., "cart", "similar", "popular"


# --- Search Schemas ---

class SearchRequest(BaseModel):
    """Schema for semantic search."""
    query: str
    limit: int = 10


class SearchResultResponse(BaseModel):
    """Schema for search result."""
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    score: float
