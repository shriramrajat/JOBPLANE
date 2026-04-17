import asyncio
import uuid
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Job, JobStatus
import redis.asyncio as redis

redis_pool = redis.ConnectionPool.from_url("redis://localhost:6379", decode_responses=True)
redis_client = redis.Redis(connection_pool=redis_pool)

async def process_job(job_id: str):
    print(f"[*] Worker received Job ID: {job_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            print(f"[!] Invalid UUID: {job_id}")
            # Even if invalid, we must clear it from processing queue or it clogs forever
            await redis_client.lrem("jobplane:queue:processing", 0, job_id)
            return
            
        result = await db.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        
        if not job:
            print(f"[!] Job {job_id} ghosted. Clearing from queue.")
            await redis_client.lrem("jobplane:queue:processing", 0, job_id)
            return

        # 2. Mark as Processing
        from sqlalchemy.sql import func
        job.status = JobStatus.PROCESSING
        job.started_at = func.now()
        await db.commit()
        print(f"[*] Job {job.id} marked as PROCESSING.")
        
        # 3. Simulate Execution
        print(f"[*] Executing payload: {job.payload}")
        await asyncio.sleep(2)
        
        # 4. Mark as Completed
        job.status = JobStatus.COMPLETED
        job.completed_at = func.now()
        await db.commit()
        
        # 5. SAFELY DEQUEUED
        # Only now, after the database is fully updated, do we wipe it from Redis
        await redis_client.lrem("jobplane:queue:processing", 0, job_id)
        
        print(f"[SUCCESS] Job {job.id} completed and wiped from Processing Queue.\n")

async def worker_loop():
    print("[*] Worker started [PHASE 2 - CRASH SAFE].")
    while True:
        # BRPOPLPUSH is the holy grail of reliable queues.
        # It blocks until an item arrives in 'main', then ATOMICALLY pushes it into 'processing'
        # before returning it to python. If Python dies at any point after this, the ID is preserved.
        job_id = await redis_client.brpoplpush("jobplane:queue:main", "jobplane:queue:processing", 0)
        
        await process_job(job_id)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        print("\n[*] Worker shutting down.")
