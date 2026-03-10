"""SQLAlchemy models + async session for scan history storage."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, Text, Integer, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Text, primary_key=True)
    url = Column(Text, nullable=False)
    config_json = Column(Text, nullable=False, default="{}")
    status = Column(Text, nullable=False, default="queued")
    phase = Column(Text, default="")
    progress = Column(Integer, default=0)
    phase_detail = Column(Text, default="")
    result_json = Column(Text, default=None)
    error = Column(Text, default=None)
    summary_json = Column(Text, default=None)
    started_at = Column(Text, default=None)
    finished_at = Column(Text, default=None)
    created_at = Column(Text, nullable=False)


def _get_db_path() -> Path:
    """Get database path at ~/.aura-privesc/scans.db."""
    db_dir = Path.home() / ".aura-privesc"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "scans.db"
    return db_path


_engine = None
_session_factory = None


async def get_engine():
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        _engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
        )
        # Set file permissions to 0600
        if db_path.exists():
            os.chmod(db_path, 0o600)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Set permissions after creation too
        if db_path.exists():
            os.chmod(db_path, 0o600)
    return _engine


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    factory = await get_session_factory()
    return factory()


async def close_db():
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
