from fastapi import APIRouter, Depends

from app.models.recap import RecapSnapshot
from app.services.recap import RecapService
from app.services.registry import get_recap_service

router = APIRouter(tags=["recap"])


@router.get("/recap", response_model=RecapSnapshot)
def recap(
    force: bool = False,
    svc: RecapService = Depends(get_recap_service),
) -> RecapSnapshot:
    if force:
        svc.invalidate()
    return svc.snapshot()
