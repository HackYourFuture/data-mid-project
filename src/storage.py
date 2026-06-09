"""Storage functions for Postgres and Blob Storage."""

import json
import logging
import os
from contextlib import closing
from datetime import datetime

import pandas as pd
import psycopg2
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

log = logging.getLogger(__name__)


def insert_readings(df: pd.DataFrame) -> None:
    """Insert a DataFrame of readings into Postgres."""
    db_url = os.environ["POSTGRES_URL"]

    with closing(psycopg2.connect(db_url)) as conn:
        cur = conn.cursor()

        # TODO: Replace 'weather_readings' with a unique name (e.g. alice_weather_readings)
        # to avoid collisions on the shared Postgres server. See Week 7 Gotcha #8.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weather_readings (
                id SERIAL PRIMARY KEY,
                city TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        for _, row in df.iterrows():
            cur.execute(
                "INSERT INTO weather_readings (city, temperature, humidity, timestamp) VALUES (%s, %s, %s, %s)",
                (row["city"], row["temperature"], row["humidity"], row["timestamp"]),
            )

        conn.commit()
        cur.close()

    log.info("Inserted %d rows into Postgres", len(df))


def upload_raw_json(raw_data) -> None:
    """Upload raw API response to Blob Storage as a JSON backup."""
    conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = BlobServiceClient.from_connection_string(conn_str)
    container = client.get_container_client("raw")
    try:
        container.create_container()
    except ResourceExistsError:
        pass

    blob_name = f"pipeline/{datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')}.json"
    container.upload_blob(
        name=blob_name,
        data=json.dumps(raw_data).encode("utf-8"),
        overwrite=True,
    )
    log.info("Uploaded raw data to blob: %s", blob_name)
