from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import icd10 as icd10_svc

router = APIRouter(prefix="/icd10", tags=["icd10"])


class ICD10Out(BaseModel):
    code: str
    description: str
    category: str
    body_part: str


@router.get("/search", response_model=list[ICD10Out])
def search(
    q: str = "",
    limit: int = 25,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ICD10Out]:
    return [
        ICD10Out(code=c.code, description=c.description, category=c.category, body_part=c.body_part)
        for c in icd10_svc.search(q, limit=limit)
    ]
