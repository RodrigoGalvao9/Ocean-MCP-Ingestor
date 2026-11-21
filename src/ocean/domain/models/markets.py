from datetime import date

from pydantic import BaseModel


class FishMarket(BaseModel):
    name: str
    kind: str  # terminal pesqueiro, mercado, entreposto, colônia...
    uf: str
    municipality: str
    latitude: float | None = None
    longitude: float | None = None
    source: str
    verified_at: date
    notes: str | None = None
