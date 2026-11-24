from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models import User
from app.services.ingestion import ingest_all

router = APIRouter(prefix="/symbols", tags=["market"])


@router.post("/{ticker}/refresh")
@limiter.limit("5/minute")
def refresh_symbol(
    request: Request,
    ticker: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticker = ticker.upper()
    results = ingest_all(db, ticker)
    if not results:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    if results[ticker] < 0:
        raise HTTPException(status_code=502, detail="Upstream data fetch failed")
    return {"ticker": ticker, "rows_upserted": results[ticker]}