import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.models.job import Job
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: str
    study_id: str
    model_name: str
    model_version: str
    status: str
    error: str | None


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return JobOut(
        id=str(j.id),
        study_id=str(j.study_id),
        model_name=j.model_name,
        model_version=j.model_version,
        status=j.status,
        error=j.error,
    )
