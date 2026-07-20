import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./videodub.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class DubbingJob(Base):
    __tablename__ = "dubbing_jobs"

    id = Column(String, primary_key=True)
    url = Column(Text, nullable=False)
    title = Column(String, nullable=True)
    source_lang = Column(String, nullable=False)
    target_lang = Column(String, nullable=False)
    voice = Column(String, nullable=False)
    whisper_model = Column(String, nullable=False)
    status = Column(String, default="pending")
    progress = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    result_path = Column(Text, nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    duration = Column(String, nullable=True)
    file_size = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with async_session() as session:
        yield session