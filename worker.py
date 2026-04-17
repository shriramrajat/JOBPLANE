import asyncio
import uuid
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Job, JobStatus
import redis.asyncio as redis

# Reusing the same Redis setup
redis_pool = redis.ConnectionPool.from_url("redis://localhost:6379", decode_responses=True)
redis_client = redis.Redis(connection_pool=redis_pool)

async def process_job(job_id: str):
    print(f"[*] Worker received Job ID: {job_id}")
    
    async with AsyncSessionLocal() as db:
        # 1. Fetch the job from Postgres
        # We parse the string back into a UUID
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            print(f"[!] Invalid UUID format received: {job_id}")
            return
            
        result = await db.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        
        if not job:
            print(f"[!] Job {job_id} not found in database. It might be a ghost.")
            return

        # 2. Mark as Processing
        job.status = JobStatus.PROCESSING
        job.started_at = func.now() if hasattr(func, "now") else None  # Will fix correct import below
        from sqlalchemy.sql import func
        job.started_at = func.now()
        
        await db.commit()
        print(f"[*] Job {job.id} marked as PROCESSING.")
        
        # 3. Simulate Execution
        print(f"[*] Executing payload: {job.payload}")
        await asyncio.sleep(2)  # Simulating heavy work
        
        # 4. Mark as Completed
        job.status = JobStatus.COMPLETED
        job.completed_at = func.now()
        await db.commit()
        
        print(f"[SUCCESS] Job {job.id} completed successfully.\n")

async def worker_loop():
    print("[*] Worker started. Listening on 'jobplane:queue:main'...")
    while True:
        # blpop is a BLOCKING pop. It waits at the Redis level until an item appears.
        # This is extremely resource efficient compared to an infinite while/sleep loop.
        queue_name, job_id = await redis_client.blpop("jobplane:queue:main")
        
        # We hand off execution. In a production worker, we would use asyncio.create_task() 
        # to process concurrently, but for Phase 1 we do it sequentially.
        await process_job(job_id)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        print("\n[*] Worker shutting down.")
