import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from .database import Base

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"  # Dead Letter Queue for terminal failure

class Job(Base):
    __tablename__ = "jobs"

    # UUID prevents ID guessing and collision across distributed writers
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # What type of job is this? e.g., 'send_email', 'process_video'
    type = Column(String, nullable=False, index=True)
    
    # Store arbitrary parameters strictly as JSONB for Postgres indexing capability
    payload = Column(JSONB, nullable=False)
    
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True)
    
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # If a worker crashes, store the stack trace here.
    last_error = Column(Text, nullable=True)
    
    # For delayed execution or exponential backoff retries.
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Note the server_default=func.now(). 
    # This forces the Postgres server's clock to set the timestamp, NOT your local python clock.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Job id={self.id} type={self.type} status={self.status}>"
