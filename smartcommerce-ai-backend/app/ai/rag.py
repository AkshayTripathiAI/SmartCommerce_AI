"""RAG (Retrieval-Augmented Generation) service for policies."""
from typing import List, Optional
from pathlib import Path
import google.generativeai as genai

from app.ai.config import ai_settings
from app.ai.embeddings import embedding_service
from app.ai.vector_store import vector_store


class RAGService:
    """Service for RAG-based policy retrieval and response generation."""
    
    def __init__(self):
        genai.configure(api_key=ai_settings.google_api_key)
        self._model = None

    @property
    def model(self):
        # Created lazily so the model name can be resolved against the live model list.
        if self._model is None:
            from app.ai.models import resolve_chat_model
            self._model = genai.GenerativeModel(resolve_chat_model())
        return self._model
    
    async def search_policies(
        self,
        query: str,
        limit: int = 3,
        policy_type: Optional[str] = None,
    ) -> List[dict]:
        """
        Search for relevant policy chunks.
        
        Args:
            query: User's question
            limit: Maximum chunks to retrieve
            policy_type: Optional filter (shipping, returns, terms)
            
        Returns:
            List of relevant policy chunks with scores
        """
        # Generate query embedding
        query_embedding = await embedding_service.get_query_embedding(query)
        
        # Search policy vectors
        results = await vector_store.search_policies(
            query_embedding=query_embedding,
            limit=limit,
            policy_type=policy_type,
        )
        
        return results
    
    async def answer_policy_question(
        self,
        question: str,
        policy_type: Optional[str] = None,
    ) -> dict:
        """
        Answer a question about policies using RAG.
        
        Args:
            question: User's question
            policy_type: Optional filter (shipping, returns, terms)
            
        Returns:
            Dict with answer and sources
        """
        # Retrieve relevant policy chunks
        chunks = await self.search_policies(
            query=question,
            limit=3,
            policy_type=policy_type,
        )
        
        if not chunks:
            return {
                "answer": "I couldn't find relevant information in our policies. Please contact customer support for assistance.",
                "sources": [],
            }
        
        # Build context from retrieved chunks
        context_parts = []
        sources = []
        for chunk in chunks:
            context_parts.append(f"[{chunk['policy_type'].upper()}]: {chunk['chunk_text']}")
            if chunk['policy_type'] not in sources:
                sources.append(chunk['policy_type'])
        
        context = "\n\n".join(context_parts)
        
        # Generate answer using Gemini
        prompt = f"""You are a helpful customer service assistant for SmartCommerce AI, an e-commerce platform.

Answer the customer's question based ONLY on the policy information provided below. Be concise, friendly, and helpful.

If the information doesn't fully answer the question, say what you can and suggest contacting customer support.

POLICY INFORMATION:
{context}

CUSTOMER QUESTION:
{question}

ANSWER:"""

        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model.generate_content(prompt)
        )
        
        return {
            "answer": response.text,
            "sources": sources,
        }


async def index_policies():
    """Index all policy documents into Qdrant."""
    policies_dir = Path(__file__).parent.parent.parent / "policies"
    
    if not policies_dir.exists():
        print(f"Policies directory not found: {policies_dir}")
        return
    
    # Ensure collection exists
    await vector_store.ensure_collections()
    
    # Process each policy file
    policy_files = list(policies_dir.glob("*.md"))
    print(f"Found {len(policy_files)} policy files")
    
    for policy_file in policy_files:
        policy_type = policy_file.stem  # e.g., "shipping", "returns"
        content = policy_file.read_text(encoding="utf-8")
        
        # Split into chunks (by sections)
        chunks = split_into_chunks(content, chunk_size=500, overlap=50)
        
        print(f"  Indexing {policy_type}: {len(chunks)} chunks")
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = await embedding_service.get_embedding(chunk)
            
            # Upsert to Qdrant
            import uuid
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{policy_type}_{i}"))
            await vector_store.upsert_policy_chunk(
                chunk_id=chunk_id,
                embedding=embedding,
                payload={
                    "policy_type": policy_type,
                    "chunk_text": chunk,
                    "chunk_index": i,
                },
            )
    
    print("✅ Policy indexing complete!")


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += ("\n\n" if current_chunk else "") + para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    # If chunks are still too large, split them further
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size * 1.5:
            # Split by sentences
            sentences = chunk.replace(". ", ".\n").split("\n")
            sub_chunk = ""
            for sentence in sentences:
                if len(sub_chunk) + len(sentence) < chunk_size:
                    sub_chunk += " " + sentence if sub_chunk else sentence
                else:
                    if sub_chunk:
                        final_chunks.append(sub_chunk.strip())
                    sub_chunk = sentence
            if sub_chunk:
                final_chunks.append(sub_chunk.strip())
        else:
            final_chunks.append(chunk)
    
    return final_chunks


# Singleton instance
rag_service = RAGService()
