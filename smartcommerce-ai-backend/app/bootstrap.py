"""One-shot startup bootstrap for demo / free-tier deployments.

When AUTO_BOOTSTRAP=true the app makes itself usable on a fresh environment:
  1. seeds categories, products and demo users if the products table is empty
  2. indexes products and policy documents into Qdrant if the collections are empty

With QDRANT_URL=":memory:" step 2 runs on every start, which takes a few seconds
and a handful of embedding calls for the small demo catalog.
"""
import logging

from sqlalchemy import func, select

from app.ai.config import ai_settings
from app.ai.vector_store import vector_store
from app.db import async_session_maker
from app.models import Product

logger = logging.getLogger(__name__)

state = {"status": "idle", "error": None}


async def run_bootstrap() -> None:
    # Imported lazily: the scripts package pulls in seed data and helpers.
    from scripts.seed_products import seed_database
    from scripts.index_vectors import index_products
    from app.ai.rag import index_policies

    state["status"] = "running"
    try:
        async with async_session_maker() as session:
            product_count = await session.scalar(select(func.count()).select_from(Product))
        if not product_count:
            logger.info("Bootstrap: seeding database")
            await seed_database()

        await vector_store.ensure_collections()
        if await vector_store.count(ai_settings.qdrant_collection_products) == 0:
            logger.info("Bootstrap: indexing products")
            await index_products()
        if await vector_store.count(ai_settings.qdrant_collection_policies) == 0:
            logger.info("Bootstrap: indexing policies")
            await index_policies()

        state["status"] = "ready"
        logger.info("Bootstrap complete")
    except Exception as e:  # keep the API up even if bootstrap fails
        state["status"] = "failed"
        state["error"] = str(e)
        logger.exception("Bootstrap failed")
