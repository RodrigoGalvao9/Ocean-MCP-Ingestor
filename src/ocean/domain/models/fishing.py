from datetime import date

from pydantic import BaseModel


class FishingClosure(BaseModel):
    """Defeso: período em que a pesca de uma espécie é proibida em uma região."""

    species: str
    uf: str | None = None
    starts_on: date
    ends_on: date
    legal_ref: str | None = None
    source_url: str | None = None


class FishingVessel(BaseModel):
    registry_id: str
    name: str
    uf: str | None = None
    vessel_type: str | None = None
    length_m: float | None = None
    authorization_status: str | None = None
