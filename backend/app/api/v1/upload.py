from io import BytesIO

import pydicom
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.studies import _run_in_new_session
from app.core.security import current_user
from app.db.models.user import User
from app.db.session import get_db
from app.dicom.validators import is_accepted_sop_class
from app.services.study_pipeline import enqueue_inference, ingest_datasets

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/dicom", status_code=202)
async def upload_dicom(
    files: list[UploadFile],
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no files")

    datasets = []
    for f in files:
        content = await f.read()
        try:
            ds = pydicom.dcmread(BytesIO(content), force=True)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"file {f.filename} is not a valid DICOM: {exc}"
            ) from exc
        if not is_accepted_sop_class(ds):
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"SOP Class {getattr(ds, 'SOPClassUID', '?')} is not accepted by this MVP",
            )
        datasets.append(ds)

    try:
        study = await ingest_datasets(
            db,
            datasets,
            actor_id=user.id,
            actor_role=user.role,
            request_id=request.headers.get("x-request-id"),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    job = enqueue_inference(db, study)
    background.add_task(_run_in_new_session, job.id)
    return {
        "study_id": str(study.id),
        "study_instance_uid": study.study_instance_uid,
        "job_id": str(job.id),
    }
