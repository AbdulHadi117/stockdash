import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Price, Symbol, User
from app.models.forecast import ForecastPoint, ForecastRun
from app.services.forecasting import WINDOW_ROWS, run_forecast


def create_run(db: Session, user: User, ticker: str, model: str, horizon: int) -> ForecastRun:
    sym = db.scalar(select(Symbol).where(Symbol.ticker == ticker.upper()))
    if sym is None:
        raise LookupError("Unknown symbol")
    rows = db.execute(
        select(Price.date, Price.adj_close)
        .where(Price.symbol_id == sym.id, Price.adj_close.is_not(None))
        .order_by(Price.date.desc())
        .limit(WINDOW_ROWS)
    ).all()[::-1]
    prices = pd.Series(
        [float(a) for _, a in rows], index=pd.to_datetime([d for d, _ in rows])
    )
    res = run_forecast(model, prices, horizon)
    run = ForecastRun(
        user_id=user.id, symbol_id=sym.id, model=model, horizon=horizon,
        params=res.params, metrics=res.metrics,
    )
    run.points = [
        ForecastPoint(date=d, yhat=y, lower=lo, upper=hi)
        for d, y, lo, hi in zip(res.dates, res.yhat, res.lower, res.upper)
    ]
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_runs(db: Session, user_id: int, limit: int = 50) -> list[ForecastRun]:
    return list(db.scalars(
        select(ForecastRun)
        .options(joinedload(ForecastRun.symbol))
        .where(ForecastRun.user_id == user_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(limit)
    ).unique())


def get_run(db: Session, user_id: int, run_id: int) -> ForecastRun | None:
    return db.scalar(
        select(ForecastRun).where(
            ForecastRun.id == run_id, ForecastRun.user_id == user_id
        )
    )