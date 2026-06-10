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
    """Convert validated records to a DataFrame and apply transformations.

    This is where pandas earns its place. Replace the examples below with
    transformations that make sense for your data.
    """
    df = pd.DataFrame([r.model_dump() for r in readings])

    # TODO: Replace these with your own transformations. Examples:
    #
    # Parse timestamp strings into proper datetime objects:
    #   df["timestamp"] = pd.to_datetime(df["timestamp"])
    #
    # Derive a new column from existing data:
    #   df["temp_fahrenheit"] = df["temperature"] * 9 / 5 + 32
    #
    # Drop rows where a required field is missing:
    #   df = df.dropna(subset=["temperature"])
    #
    # Rename columns to match your Postgres table:
    #   df = df.rename(columns={"timestamp": "recorded_at"})

    log.info("Transformed %d rows", len(df))
    return df


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
