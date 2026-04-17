import uuid
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from database import get_db
from models import Job, JobStatus
import redis.asyncio as redis

# Connecting to local Redis. In production, read from an environment variable!
redis_pool = redis.ConnectionPool.from_url("redis://localhost:6379", decode_responses=True)
redis_client = redis.Redis(connection_pool=redis_pool)

app = FastAPI(title="JobPlane API")

class JobCreateRequest(BaseModel):
    type: str
    payload: Dict[str, Any]
    max_retries: int = 3

@app.post("/jobs", status_code=201)
async def create_job(request: JobCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    Submission flow strictly follows the 'Database First' reconciliation pattern.
    """
    # 1. Source of Truth: Save to PostgreSQL
    new_job = Job(
        type=request.type,
        payload=request.payload,
        status=JobStatus.QUEUED,
        max_retries=request.max_retries
    )
    db.add(new_job)
    
    try:
        await db.commit()
        await db.refresh(new_job)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Fatal: Failed to save job to database")

    # 2. Best-Effort Enqueue: Push to Redis
    try:
        await redis_client.rpush("jobplane:queue:main", str(new_job.id))
    except Exception as e:
        # We catch the error but DO NOT fail the HTTP request. 
        # The job is safely persisted in Postgres as QUEUED. 
        # Our future "Sweeper" service will find it and retry exactly this Redis push.
        print(f"CRITICAL: Redis Enqueue Failed for Job {new_job.id}. Awaiting Sweeper. Error: {e}")
    
    return {"job_id": str(new_job.id), "status": new_job.status}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Fetches real-time status strictly from Postgres, not Redis."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job plainly does not exist.")
        
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "retry_count": job.retry_count,
        "created_at": job.created_at
    }
