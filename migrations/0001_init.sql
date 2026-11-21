-- Esquema inicial (v0.1). Posições geográficas como latitude/longitude simples;
-- PostGIS é opcional e pode entrar depois.

CREATE TABLE tide_stations (
    id            text PRIMARY KEY,
    name          text NOT NULL,
    uf            text,
    latitude      double precision NOT NULL,
    longitude     double precision NOT NULL,
    chart_number  text,
    timezone      text NOT NULL DEFAULT 'America/Sao_Paulo',
    datum_note    text
);

CREATE TABLE tide_events (
    station_id  text NOT NULL REFERENCES tide_stations (id) ON DELETE CASCADE,
    event_at    timestamptz NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('high', 'low')),
    height_m    numeric(5, 2) NOT NULL,
    edition     integer,
    PRIMARY KEY (station_id, event_at, kind)
);
CREATE INDEX tide_events_at_idx ON tide_events (station_id, event_at);

CREATE TABLE fishing_closures (
    id           bigserial PRIMARY KEY,
    species      text NOT NULL,
    uf           text,
    starts_on    date NOT NULL,
    ends_on      date NOT NULL,
    legal_ref    text,
    source_url   text,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (species, uf, starts_on, ends_on)
);

CREATE TABLE fishing_vessels (
    registry_id           text PRIMARY KEY,
    name                  text NOT NULL,
    uf                    text,
    vessel_type           text,
    length_m              numeric(6, 2),
    authorization_status  text,
    source                text,
    updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX fishing_vessels_name_idx ON fishing_vessels (lower(name));

CREATE TABLE fish_markets (
    id            bigserial PRIMARY KEY,
    name          text NOT NULL,
    kind          text NOT NULL,
    uf            text NOT NULL,
    municipality  text NOT NULL,
    latitude      double precision,
    longitude     double precision,
    source        text NOT NULL,
    verified_at   date NOT NULL,
    notes         text,
    UNIQUE (name, municipality, uf)
);

CREATE TABLE ingestion_runs (
    id              bigserial PRIMARY KEY,
    job             text NOT NULL,
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    status          text NOT NULL,
    rows_affected   integer NOT NULL DEFAULT 0,
    error           text,
    source_version  text
);
CREATE INDEX ingestion_runs_job_idx ON ingestion_runs (job, started_at DESC);
