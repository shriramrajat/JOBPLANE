import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# We define the DB URL via environment variable. 
# You shouldn't hardcode this if you actually plan to run a distributed system.
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:NewStrongPassword123@localhost:5432/jobplane"
)

# create_async_engine handles the connection pool under the hood.
engine = create_async_engine(DATABASE_URL, echo=False)

# AsyncSession is mandatory because our driver is asyncpg.
AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """Dependency injection for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        yield session
