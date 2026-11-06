from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from app.config import settings


def _normalize_async_url(url: str):
    """Accept plain postgres URLs (e.g. from Neon/Render) and adapt them for asyncpg.

    asyncpg does not understand libpq query params such as sslmode/channel_binding,
    so they are stripped and SSL is passed through connect_args instead.
    """
    connect_args = {}
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = "require"
    url = urlunsplit(parts._replace(query=urlencode(query)))
    return url, connect_args


_db_url, _connect_args = _normalize_async_url(settings.database_url)

# Create async engine
engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,  # serverless Postgres (e.g. Neon) drops idle connections
    connect_args=_connect_args,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
