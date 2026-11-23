from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel


class FishingClosure(BaseModel):
    """Defeso: período anual em que a pesca de uma espécie é proibida.

    `prohibition_start` e `prohibition_end` são 'MM-DD'. Se o fim vier antes do início, o período
    atravessa a virada do ano (lagosta: 11-01 a 04-30). `year` preenchido restringe o período
    ao ano em que ele começa (caranguejo-uçá, cujas datas mudam a cada ano).
    """

    species: str
    scientific_name: str | None = None
    region: str | None = None
    environment: str = "marine"  # marine ou continental
    prohibition_start: str
    prohibition_end: str
    year: int | None = None
    fishing_type: str | None = None
    legal_reference: str
    source_url: str | None = None
    source_type: str = "official"
    last_verified_at: date | None = None
    notes: str | None = None


class FishingVessel(BaseModel):
    registry_id: str
    name: str
    uf: str | None = None
    vessel_type: str | None = None
    length_m: float | None = None
    authorization_status: str | None = None


@dataclass
class LoadedClosure:
    closure: FishingClosure
    areas: dict[tuple[str, str], str | None] = field(default_factory=dict)  # (uf, ibge) -> nome

    @property
    def natural_key(self) -> tuple[str, str, str, str, str, int]:
        """Mesma norma, espécie (nome popular + científico), período e ano = o mesmo defeso."""
        c = self.closure
        return (
            c.legal_reference,
            c.species,
            c.scientific_name or "",
            c.prohibition_start,
            c.prohibition_end,
            c.year or 0,
        )
