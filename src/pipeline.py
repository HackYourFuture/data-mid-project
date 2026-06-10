"""Main pipeline: fetch, validate, store."""

import logging
import os
import sys

import pandas as pd
from pydantic import ValidationError

from src.models import WeatherReading
from src.storage import insert_readings, upload_raw_json

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("azure").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


def fetch_data() -> list[dict]:
    """Fetch data from your API. Replace this with your own logic."""
    # TODO: Replace with your API call
    # Example using requests:
    #   response = requests.get("https://api.open-meteo.com/v1/forecast?...")
    #   response.raise_for_status()
    #   return response.json()["hourly"]
    raise NotImplementedError("Replace this with your API call")


def validate(raw_records: list[dict]) -> list[WeatherReading]:
    """Validate raw records using Pydantic models."""
    valid = []
    for record in raw_records:
        try:
            valid.append(WeatherReading(**record))
        except ValidationError as e:
            log.warning("Skipping invalid record: %s", e)
    log.info("Validated %d / %d records", len(valid), len(raw_records))
    return valid


def transform(readings: list[WeatherReading]) -> pd.DataFrame:
    """Convert validated records to a DataFrame. Add any transformations here."""
    # TODO: Add your own transformations (unit conversions, derived columns, etc.)
    return pd.DataFrame([r.model_dump() for r in readings])


def run():
    """Run the full pipeline: fetch -> validate -> transform -> store."""
    log.info("Pipeline starting")

    raw = fetch_data()
    readings = validate(raw)

    if not readings:
        log.error("No valid records to store")
        sys.exit(1)

    df = transform(readings)
    insert_readings(df)
    upload_raw_json(raw)

    log.info("Pipeline finished: %d records stored", len(df))


if __name__ == "__main__":
    # Fail fast if required env vars are missing
    for var in ["POSTGRES_URL", "AZURE_STORAGE_CONNECTION_STRING"]:
        if var not in os.environ:
            log.error("Missing required environment variable: %s", var)
            sys.exit(1)

    run()
