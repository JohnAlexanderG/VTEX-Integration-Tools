"""
Async SQLAlchemy database setup.
DATABASE_URL se carga desde el .env raíz del proyecto (via main.py → load_dotenv).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Cargar .env explícitamente para cuando database.py se importa antes que main.py
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vtex_app:password@localhost:5432/vtex_integration",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency que cede una sesión async de BD."""
    async with AsyncSessionLocal() as session:
        yield session
