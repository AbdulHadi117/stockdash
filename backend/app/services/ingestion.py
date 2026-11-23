import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Price, Symbol

log = logging.getLogger(__name__)

HISTORY_YEARS = 5
COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def _start_date(db: Session, symbol_id: int) -> date:
    last = db.scalar(select(func.max(Price.date)).where(Price.symbol_id == symbol_id))
    return last if last else date.today() - timedelta(days=365 * HISTORY_YEARS)


def _fetch(ticker: str, start: date) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=False, actions=False)
    if df.empty:
        return df
    df = df.rename(columns=COLUMNS)[list(COLUMNS.values())].dropna(subset=["close"])
    df["volume"] = df["volume"].fillna(0)
    df.index = df.index.date
    return df


def ingest_symbol(db: Session, symbol: Symbol) -> int:
    df = _fetch(symbol.ticker, _start_date(db, symbol.id))
    if df.empty:
        log.warning("%s: no data returned", symbol.ticker)
        return 0
    rows = [
        {
            "symbol_id": symbol.id,
            "date": d,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "adj_close": float(r.adj_close),
            "volume": int(r.volume),
        }
        for d, r in zip(df.index, df.itertuples(index=False))
    ]
    stmt = insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol_id", "date"],
        set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "adj_close", "volume")},
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def ingest_all(db: Session, ticker: str | None = None) -> dict[str, int]:
    stmt = select(Symbol).order_by(Symbol.ticker)
    if ticker:
        stmt = stmt.where(Symbol.ticker == ticker)
    results: dict[str, int] = {}
    for symbol in db.scalars(stmt).all():
        name = symbol.ticker
        try:
            results[name] = ingest_symbol(db, symbol)
        except Exception:
            db.rollback()
            log.exception("%s: ingestion failed", name)
            results[name] = -1
    return results