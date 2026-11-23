import argparse
import logging

from app.core.database import SessionLocal
from app.services.ingestion import ingest_all
from app.services.seed import seed_symbols


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--ticker")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.command == "seed":
            print(f"Seeded {seed_symbols(db)} symbols")
        else:
            for ticker, count in ingest_all(db, args.ticker).items():
                print(f"{ticker}: {'FAILED' if count < 0 else count} rows")


if __name__ == "__main__":
    main()