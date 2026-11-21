from dataclasses import dataclass


@dataclass(frozen=True)
class JobResult:
    rows: int = 0
    source_version: str | None = None
