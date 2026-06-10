"""Example tests for Pydantic models. Replace with your own."""

import pytest
from pydantic import ValidationError
from src.models import WeatherReading


def test_valid_reading():
    """A valid record should be accepted."""
    reading = WeatherReading(
        city="Copenhagen",
        temperature=18.5,
        humidity=65.0,
        timestamp="2026-03-30T10:00",
    )
    assert reading.city == "Copenhagen"
    assert reading.temperature == 18.5


def test_invalid_temperature_too_high():
    """Temperature above 100 should be rejected."""
    with pytest.raises(ValidationError):
        WeatherReading(
            city="Copenhagen",
            temperature=999,
            humidity=65.0,
            timestamp="2026-03-30T10:00",
        )


def test_missing_city():
    """Missing required field should be rejected."""
    with pytest.raises(ValidationError):
        WeatherReading(
            temperature=18.5,
            humidity=65.0,
            timestamp="2026-03-30T10:00",
        )
