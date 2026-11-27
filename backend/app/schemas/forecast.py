import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ForecastRequest(BaseModel):
    ticker: str = Field(pattern=r"^[\^A-Za-z0-9.\-]{1,12}$")
    model: Literal["arima", "xgboost"]
    horizon: int = Field(ge=1, le=30)


class ForecastPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: dt.date
    yhat: float
    lower: float
    upper: float


class ForecastRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    model: str
    horizon: int
    metrics: dict
    created_at: dt.datetime


class ForecastRunOut(ForecastRunSummary):
    params: dict
    points: list[ForecastPointOut]