import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models import User
from app.schemas.forecast import ForecastRequest, ForecastRunOut, ForecastRunSummary
from app.services import forecast_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("", response_model=ForecastRunOut, status_code=201)
@limiter.limit("10/minute")
def create_forecast(
    request: Request,
    body: ForecastRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return forecast_service.create_run(db, user, body.ticker, body.model, body.horizon)
    except LookupError:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        log.exception("Forecast failed")
        raise HTTPException(status_code=500, detail="Forecast failed")


@router.get("", response_model=list[ForecastRunSummary])
@limiter.limit("60/minute")
def list_forecasts(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return forecast_service.list_runs(db, user.id)


@router.get("/{run_id}", response_model=ForecastRunOut)
@limiter.limit("60/minute")
def get_forecast(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = forecast_service.get_run(db, user.id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    return run