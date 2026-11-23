import datetime as dt

from sqlalchemy import BigInteger, Date, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Price(Base):
    __tablename__ = "prices"

    symbol_id: Mapped[int] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)