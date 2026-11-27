import datetime as dt
from pydantic import BaseModel, ConfigDict


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    name: str | None = None
    region: str | None = None
    currency: str | None = None
    asset_type: str | None = None


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: dt.date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: float | None = None


class SummaryOut(BaseModel):
    ticker: str
    name: str | None = None
    as_of: dt.date
    close: float | None = None
    prev_close: float | None = None
    change_pct: float | None = None