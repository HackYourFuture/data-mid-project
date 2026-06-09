"""Pydantic models for data validation. Replace with your own."""

from pydantic import BaseModel, Field


class WeatherReading(BaseModel):
    """Example model. Replace with your own data structure."""

    city: str
    temperature: float = Field(ge=-100, le=100)
    humidity: float = Field(ge=0, le=100)
    timestamp: str

    # TODO: Replace these fields with the fields from your API response.
    # Pydantic will reject any record that does not match this schema.
