"""Qdrant vector database client and operations."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from app.ai.config import ai_settings


class VectorStore:
    """Qdrant vector store for product and policy embeddings."""
    
    def __init__(self):
        self._client: Optional[AsyncQdrantClient] = None
    
    async def get_client(self) -> AsyncQdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            if ai_settings.qdrant_url == ":memory:":
                self._client = AsyncQdrantClient(location=":memory:")
            else:
                self._client = AsyncQdrantClient(
                    url=ai_settings.qdrant_url,
                    api_key=ai_settings.qdrant_api_key or None,
                )
        return self._client
    
    async def count(self, collection_name: str) -> int:
        """Number of points in a collection (0 if it does not exist)."""
        client = await self.get_client()
        try:
            result = await client.count(collection_name=collection_name)
            return result.count
        except Exception:
            return 0
    
    async def ensure_collections(self):
        """Ensure required collections exist."""
        client = await self.get_client()
        
        collections = [
            ai_settings.qdrant_collection_products,
            ai_settings.qdrant_collection_policies,
        ]
        
        existing = await client.get_collections()
        existing_names = {c.name for c in existing.collections}
        
        for collection_name in collections:
            if collection_name not in existing_names:
                await client.create_collection(
                    collection_name=collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=ai_settings.embedding_dimensions,  # 768 for Gemini
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                print(f"Created collection: {collection_name}")
    
    async def upsert_product(
        self,
        product_id: UUID,
        embedding: List[float],
        payload: Dict[str, Any],
    ):
        """Upsert a product embedding."""
        client = await self.get_client()
        
        await client.upsert(
            collection_name=ai_settings.qdrant_collection_products,
            points=[
                qdrant_models.PointStruct(
                    id=str(product_id),
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
    
    async def upsert_products_batch(
        self,
        products: List[Dict[str, Any]],
    ):
        """
        Batch upsert product embeddings.
        
        Args:
            products: List of dicts with 'id', 'embedding', and 'payload' keys
        """
        client = await self.get_client()
        
        points = [
            qdrant_models.PointStruct(
                id=str(p["id"]),
                vector=p["embedding"],
                payload=p["payload"],
            )
            for p in products
        ]
        
        await client.upsert(
            collection_name=ai_settings.qdrant_collection_products,
            points=points,
        )
    
    async def upsert_policy_chunk(
        self,
        chunk_id: str,
        embedding: List[float],
        payload: Dict[str, Any],
    ):
        """Upsert a policy chunk embedding."""
        client = await self.get_client()
        
        await client.upsert(
            collection_name=ai_settings.qdrant_collection_policies,
            points=[
                qdrant_models.PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
    
    async def search_products(
        self,
        query_embedding: List[float],
        limit: int = 10,
        score_threshold: float = 0.5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar products.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional filter conditions
            
        Returns:
            List of products with scores
        """
        client = await self.get_client()
        
        # Build filter if provided
        qdrant_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, bool):
                    must_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value),
                        )
                    )
                elif isinstance(value, (int, float)):
                    must_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value),
                        )
                    )
                elif isinstance(value, str):
                    must_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value),
                        )
                    )
            if must_conditions:
                qdrant_filter = qdrant_models.Filter(must=must_conditions)
        
        results = await client.search(
            collection_name=ai_settings.qdrant_collection_products,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                **result.payload,
            }
            for result in results
        ]
    
    async def search_policies(
        self,
        query_embedding: List[float],
        limit: int = 5,
        policy_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant policy chunks.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            policy_type: Optional filter by policy type
            
        Returns:
            List of policy chunks with scores
        """
        client = await self.get_client()
        
        qdrant_filter = None
        if policy_type:
            qdrant_filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="policy_type",
                        match=qdrant_models.MatchValue(value=policy_type),
                    )
                ]
            )
        
        results = await client.search(
            collection_name=ai_settings.qdrant_collection_policies,
            query_vector=query_embedding,
            limit=limit,
            query_filter=qdrant_filter,
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                **result.payload,
            }
            for result in results
        ]
    
    async def get_product_by_id(self, product_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a product embedding by ID."""
        client = await self.get_client()
        
        results = await client.retrieve(
            collection_name=ai_settings.qdrant_collection_products,
            ids=[str(product_id)],
            with_vectors=True,
        )
        
        if results:
            point = results[0]
            return {
                "id": point.id,
                "embedding": point.vector,
                **point.payload,
            }
        return None
    
    async def delete_product(self, product_id: UUID):
        """Delete a product from the vector store."""
        client = await self.get_client()
        
        await client.delete(
            collection_name=ai_settings.qdrant_collection_products,
            points_selector=qdrant_models.PointIdsList(
                points=[str(product_id)],
            ),
        )
    
    async def close(self):
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Singleton instance
vector_store = VectorStore()
