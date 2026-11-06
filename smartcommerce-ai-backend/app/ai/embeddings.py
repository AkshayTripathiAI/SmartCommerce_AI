"""Embedding service using Google Gemini."""
import hashlib
from typing import List, Optional
import google.generativeai as genai

from app.ai.config import ai_settings
from app.core.kv import get_kv


class EmbeddingService:
    """Service for generating and caching embeddings using Gemini."""
    
    def __init__(self):
        genai.configure(api_key=ai_settings.google_api_key)
        self.model = ai_settings.embedding_model
        self.dimensions = ai_settings.embedding_dimensions
    
    async def get_redis(self):
        """Get the cache client (Redis or in-process fallback)."""
        return get_kv(decode_responses=False)
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"embedding:{self.model}:{text_hash}"
    
    async def get_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Get embedding for a single text using Gemini.
        
        Args:
            text: Text to embed
            use_cache: Whether to use Redis cache
            
        Returns:
            List of floats representing the embedding
        """
        if not text.strip():
            return [0.0] * self.dimensions
        
        # Try cache first
        if use_cache:
            try:
                redis_client = await self.get_redis()
                cache_key = self._cache_key(text)
                cached = await redis_client.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass  # Cache miss or error, proceed with API call
        
        # Call Gemini API (sync call wrapped)
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=self.dimensions,
            )
        )
        
        embedding = result["embedding"]
        
        # Cache the result
        if use_cache:
            try:
                import json
                redis_client = await self.get_redis()
                cache_key = self._cache_key(text)
                await redis_client.setex(
                    cache_key,
                    86400 * 7,  # 7 days TTL
                    json.dumps(embedding),
                )
            except Exception:
                pass  # Cache write failed, but we have the embedding
        
        return embedding
    
    async def get_embeddings_batch(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """
        Get embeddings for multiple texts using Gemini.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use Redis cache
            
        Returns:
            List of embeddings
        """
        if not texts:
            return []
        
        # Check cache for all texts
        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []
        
        if use_cache:
            try:
                redis_client = await self.get_redis()
                import json
                for i, text in enumerate(texts):
                    if not text.strip():
                        results[i] = [0.0] * self.dimensions
                        continue
                    cache_key = self._cache_key(text)
                    cached = await redis_client.get(cache_key)
                    if cached:
                        results[i] = json.loads(cached)
                    else:
                        texts_to_embed.append(text)
                        indices_to_embed.append(i)
            except Exception:
                # Cache error, embed all texts
                texts_to_embed = [t for t in texts if t.strip()]
                indices_to_embed = [i for i, t in enumerate(texts) if t.strip()]
                for i, t in enumerate(texts):
                    if not t.strip():
                        results[i] = [0.0] * self.dimensions
        else:
            texts_to_embed = [t for t in texts if t.strip()]
            indices_to_embed = [i for i, t in enumerate(texts) if t.strip()]
            for i, t in enumerate(texts):
                if not t.strip():
                    results[i] = [0.0] * self.dimensions
        
        # Embed remaining texts using Gemini batch API
        if texts_to_embed:
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Gemini supports batch embedding
            response = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=self.model,
                    content=texts_to_embed,
                    task_type="retrieval_document",
                    output_dimensionality=self.dimensions,
                )
            )
            
            embeddings = response["embedding"]
            
            # Handle both single and batch responses
            if texts_to_embed and len(texts_to_embed) == 1:
                embeddings = [embeddings]
            
            for idx, embedding in zip(indices_to_embed, embeddings):
                results[idx] = embedding
                
                # Cache the result
                if use_cache:
                    try:
                        import json
                        redis_client = await self.get_redis()
                        cache_key = self._cache_key(texts[idx])
                        await redis_client.setex(
                            cache_key,
                            86400 * 7,
                            json.dumps(embedding),
                        )
                    except Exception:
                        pass
        
        return results
    
    async def get_query_embedding(self, query: str, use_cache: bool = True) -> List[float]:
        """
        Get embedding for a search query (uses retrieval_query task type).
        
        Args:
            query: Search query
            use_cache: Whether to use Redis cache
            
        Returns:
            List of floats representing the embedding
        """
        if not query.strip():
            return [0.0] * self.dimensions
        
        cache_key = f"query:{self._cache_key(query)}"
        
        # Try cache first
        if use_cache:
            try:
                redis_client = await self.get_redis()
                cached = await redis_client.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass
        
        # Call Gemini API with query task type
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=self.model,
                content=query,
                task_type="retrieval_query",
                output_dimensionality=self.dimensions,
            )
        )
        
        embedding = result["embedding"]
        
        # Cache the result
        if use_cache:
            try:
                import json
                redis_client = await self.get_redis()
                await redis_client.setex(
                    cache_key,
                    86400,  # 1 day TTL for queries
                    json.dumps(embedding),
                )
            except Exception:
                pass
        
        return embedding
    
    async def close(self):
        """Nothing to close: the cache client is shared (see app.core.kv)."""


# Singleton instance
embedding_service = EmbeddingService()
