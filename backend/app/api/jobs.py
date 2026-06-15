from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.tasks import celery

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobStatus(BaseModel):
    task_id: str
    status: str
    ready: bool


@router.get("/{task_id}", response_model=JobStatus)
async def get_job_status(task_id: str) -> JobStatus:
    result = celery.AsyncResult(task_id)
    return JobStatus(
        task_id=task_id,
        status=result.state.lower(),
        ready=result.ready(),
    )
