from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Symbol

SYMBOLS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "GOOG", "name": "Alphabet Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "AMD", "name": "Advanced Micro Devices, Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "MU", "name": "Micron Technology, Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "SMCI", "name": "Super Micro Computer, Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "C", "name": "Citigroup Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "HPQ", "name": "HP Inc.", "region": "US", "currency": "USD", "asset_type": "stock"},
    {"ticker": "^GSPC", "name": "S&P 500", "region": "US", "currency": "USD", "asset_type": "index"},
    {"ticker": "^DJI", "name": "Dow Jones Industrial Average", "region": "US", "currency": "USD", "asset_type": "index"},
    {"ticker": "^IXIC", "name": "NASDAQ Composite", "region": "US", "currency": "USD", "asset_type": "index"},
    {"ticker": "^GDAXI", "name": "DAX", "region": "Germany", "currency": "EUR", "asset_type": "index"},
    {"ticker": "^FCHI", "name": "CAC 40", "region": "France", "currency": "EUR", "asset_type": "index"},
    {"ticker": "^HSI", "name": "Hang Seng Index", "region": "Hong Kong", "currency": "HKD", "asset_type": "index"},
    {"ticker": "^BSESN", "name": "S&P BSE SENSEX", "region": "India", "currency": "INR", "asset_type": "index"},
]


def seed_symbols(db: Session) -> int:
    stmt = insert(Symbol).values(SYMBOLS)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_={c: stmt.excluded[c] for c in ("name", "region", "currency", "asset_type")},
    )
    db.execute(stmt)
    db.commit()
    return len(SYMBOLS)