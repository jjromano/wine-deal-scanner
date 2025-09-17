"""Data models for the wine deal scanner."""

from pydantic import BaseModel, Field


class Deal(BaseModel):
    """Represents a wine deal from LastBottle."""

    title: str = Field(..., description="Wine name/title")
    price: float = Field(..., gt=0, description="Current sale price")
    bottle_size_ml: int = Field(750, description="Bottle size in milliliters")
    url: str = Field(..., description="URL to the deal page")

    def __str__(self) -> str:
        """String representation of the deal."""
        return f"{self.title}: ${self.price:.2f}"