"""Data models for the wine deal scanner."""

import re

from pydantic import BaseModel, Field


class Deal(BaseModel):
    """Represents a wine deal from LastBottle."""

    title: str = Field(..., description="Wine name/title")
    price: float = Field(..., gt=0, description="Current sale price")
    list_price: float | None = Field(None, gt=0, description="Original list price")
    vintage: str | None = Field(None, description="Wine vintage year")
    region: str | None = Field(None, description="Wine region")
    url: str = Field(..., description="URL to the deal page")
    bottle_size_ml: int = Field(750, description="Bottle size in milliliters")

    def __str__(self) -> str:
        """String representation of the deal."""
        vintage_str = f" ({self.vintage})" if self.vintage else ""
        region_str = f" - {self.region}" if self.region else ""
        list_price_str = f" (was ${self.list_price:.2f})" if self.list_price else ""

        return f"{self.title}{vintage_str}{region_str}: ${self.price:.2f}{list_price_str}"


class VivinoData(BaseModel):
    """Vivino enrichment data for a wine."""

    rating: float | None = Field(None, ge=0, le=5, description="Average rating (0-5)")
    rating_count: int | None = Field(None, ge=0, description="Number of ratings")
    avg_price: float | None = Field(None, gt=0, description="Average price on Vivino")

    def __str__(self) -> str:
        """String representation of Vivino data."""
        parts = []
        if self.rating is not None:
            parts.append(f"★{self.rating:.1f}")
        if self.rating_count is not None:
            parts.append(f"({self.rating_count} reviews)")
        if self.avg_price is not None:
            parts.append(f"avg ${self.avg_price:.2f}")

        return " ".join(parts) if parts else "No Vivino data"


class DealDetails(BaseModel):
    """Deal details extracted from LastBottle page HTML."""

    wine_name: str = Field(..., description="Name of the wine")
    vintage: int | None = Field(None, description="Wine vintage year")
    bottle_size_ml: int = Field(750, description="Bottle size in milliliters")
    deal_price: float = Field(..., gt=0, description="LastBottle deal price")

    def __str__(self) -> str:
        """String representation of deal details."""
        vintage_str = f" {self.vintage}" if self.vintage else ""
        size_str = f" ({self.bottle_size_ml}ml)" if self.bottle_size_ml != 750 else ""
        return f"{self.wine_name}{vintage_str}{size_str}: ${self.deal_price:.2f}"


class EnrichedDeal(BaseModel):
    """Deal enriched with Vivino data."""

    # Core deal information
    wine_name: str = Field(..., description="Name of the wine")
    vintage: int | None = Field(None, description="Wine vintage year")
    bottle_size_ml: int = Field(750, description="Bottle size in milliliters")
    deal_price: float = Field(..., gt=0, description="LastBottle deal price")

    # Vivino vintage-specific data
    vintage_rating: float | None = Field(None, ge=1, le=5, description="Vivino rating for specific vintage")
    vintage_price: float | None = Field(None, gt=0, description="Vivino average price for specific vintage")
    vintage_reviews: int | None = Field(None, ge=0, description="Number of Vivino reviews for specific vintage")

    # Vivino overall wine data
    overall_rating: float | None = Field(None, ge=1, le=5, description="Vivino overall wine rating")
    overall_price: float | None = Field(None, gt=0, description="Vivino overall average price")
    overall_reviews: int | None = Field(None, ge=0, description="Number of Vivino overall reviews")

    def __str__(self) -> str:
        """String representation of enriched deal."""
        vintage_str = f" {self.vintage}" if self.vintage else ""
        size_str = f" ({self.bottle_size_ml}ml)" if self.bottle_size_ml != 750 else ""

        # Build rating information
        rating_parts = []
        if self.vintage_rating:
            rating_parts.append(f"Vintage: {self.vintage_rating:.1f}★")
        if self.overall_rating:
            rating_parts.append(f"Overall: {self.overall_rating:.1f}★")

        rating_str = f" [{', '.join(rating_parts)}]" if rating_parts else ""

        return f"{self.wine_name}{vintage_str}{size_str}: ${self.deal_price:.2f}{rating_str}"

    @property
    def has_vivino_data(self) -> bool:
        """Check if any Vivino data is available."""
        return any([
            self.vintage_rating, self.vintage_price, self.vintage_reviews,
            self.overall_rating, self.overall_price, self.overall_reviews
        ])

    @property
    def best_rating(self) -> float | None:
        """Get the best available rating (vintage-specific preferred)."""
        return self.vintage_rating or self.overall_rating

    @property
    def best_price_comparison(self) -> dict[str, float | None]:
        """Compare deal price with Vivino prices."""
        vivino_price = self.vintage_price or self.overall_price

        if not vivino_price:
            return {"vivino_price": None, "savings": None, "savings_percent": None}

        savings = vivino_price - self.deal_price
        savings_percent = (savings / vivino_price) * 100 if vivino_price > 0 else 0

        return {
            "vivino_price": vivino_price,
            "savings": savings,
            "savings_percent": savings_percent
        }


# Bottle size detection patterns and helper function
# Order matters - more specific patterns should come first
_SIZE_PATTERNS = [
    (r"\b(187)\s*ml\b|\b(split|piccolo)\b", 187),
    (r"\b(375)\s*ml\b|\b(0\.375)\s*l\b|\b(half|demi)\b", 375),
    (r"\b(500)\s*ml\b|\b(0\.5)\s*l\b", 500),
    (r"\b(620)\s*ml\b", 620),  # odd sizes, keep just in case
    (r"\b(720)\s*ml\b", 720),
    (r"\b(750)\s*ml\b|\b(0\.75)\s*l\b", 750),
    (r"\b1\s*l\b|\b1000\s*ml\b", 1000),
    # More specific patterns for double magnum first
    (r"\bdouble\s+magnum\s+3\s*l\b", 3000),
    (r"\bdouble\s+magnum\b", 3000),
    (r"\b3\s*l\b|\b3000\s*ml\b|\bjeroboam\b", 3000),
    (r"\b6\s*l\b|\b6000\s*ml\b|\b(imperial)\b", 6000),
    # Regular magnum last so it doesn't interfere with double magnum
    (r"\b1\.5\s*l\b|\b1500\s*ml\b|\bmagnum\b", 1500),
]


def normalize_bottle_size(text: str | None) -> int:
    """
    Parse bottle size from free text (title/size label).
    Returns size in milliliters; defaults to 750 if not found.
    Recognizes common formats: '375ml', '0.375L', 'half/demi', 'magnum/1.5L', 'double magnum/3L', etc.
    """
    if not text:
        return 750
    t = text.lower()
    for pat, ml in _SIZE_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return ml
    # Fallback: generic "X L" or "X ml" if present
    m_l = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*l\b", t)
    if m_l:
        try:
            liters = float(m_l.group(1))
            # Only accept reasonable wine bottle sizes
            if 0.1 <= liters <= 6.0:
                return int(round(liters * 1000))
        except Exception:
            pass
    m_ml = re.search(r"\b([0-9]{2,4})\s*ml\b", t)
    if m_ml:
        try:
            ml_val = int(m_ml.group(1))
            if 100 <= ml_val <= 6000:
                return ml_val
        except Exception:
            pass
    return 750
