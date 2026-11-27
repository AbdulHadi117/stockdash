import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models import User, Price, Symbol
from app.schemas.market import PriceOut, SummaryOut,SymbolOut
from app.services.ingestion import ingest_all

router = APIRouter(prefix="/symbols", tags=["market"])
market_router = APIRouter(prefix="/market", tags=["market"])

@router.get("", response_model=list[SymbolOut])
@limiter.limit("60/minute")
def list_symbols(request: Request, db: Session = Depends(get_db)):
    return db.scalars(
        select(Symbol).order_by(Symbol.asset_type, Symbol.ticker)
    ).all()

@market_router.get("/summary", response_model=list[SummaryOut])
@limiter.limit("30/minute")
def market_summary(request: Request, db: Session = Depends(get_db)):
    rn = func.row_number().over(
        partition_by=Price.symbol_id, order_by=Price.date.desc()
    ).label("rn")
    sub = select(Price.symbol_id, Price.date, Price.close, rn).subquery()
    rows = db.execute(
        select(Symbol.ticker, Symbol.name, sub.c.date, sub.c.close, sub.c.rn)
        .join(sub, sub.c.symbol_id == Symbol.id)
        .where(sub.c.rn <= 2)
        .order_by(Symbol.ticker, sub.c.rn)
    ).all()
    out: dict[str, dict] = {}
    for ticker, name, d, close, r in rows:
        if r == 1:
            out[ticker] = {"ticker": ticker, "name": name, "as_of": d,
                           "close": close, "prev_close": None, "change_pct": None}
        elif ticker in out:
            out[ticker]["prev_close"] = close
            c = out[ticker]["close"]
            if close and c is not None:
                out[ticker]["change_pct"] = (c / close - 1) * 100
    return list(out.values())

@router.get("/{ticker}/prices", response_model=list[PriceOut])
@limiter.limit("60/minute")
def get_prices(
    request: Request,
    ticker: str,
    start: dt.date | None = None,
    end: dt.date | None = None,
    db: Session = Depends(get_db),
):
    sym = db.scalar(select(Symbol).where(Symbol.ticker == ticker.upper()))
    if sym is None:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be <= end")
    q = select(Price).where(Price.symbol_id == sym.id)
    if start:
        q = q.where(Price.date >= start)
    if end:
        q = q.where(Price.date <= end)
    return db.scalars(q.order_by(Price.date)).all()


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