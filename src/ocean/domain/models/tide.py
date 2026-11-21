from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TideStation(BaseModel):
    id: str
    name: str
    uf: str | None = None
    latitude: float
    longitude: float
    chart_number: str | None = None
    timezone: str = "America/Sao_Paulo"
    datum_note: str | None = None


class TideEvent(BaseModel):
    station_id: str
    at: datetime  # instante absoluto (UTC)
    kind: Literal["high", "low"]  # preamar ou baixa-mar
    height_m: float
    edition: int | None = None  # edição da tábua (ex.: 63 para a Tábuas das Marés 2026)
