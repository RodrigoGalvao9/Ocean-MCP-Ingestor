from pydantic import BaseModel


class Place(BaseModel):
    name: str
    uf: str
    kind: str  # cidade, porto ou ilha
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        return f"{self.name} ({self.uf})"
