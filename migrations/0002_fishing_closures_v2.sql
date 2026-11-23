-- Defeso (fase 3): período que se repete todo ano (dia-mês), com área por município.
-- A tabela fishing_closures da 0001 nunca foi carregada (o job era um esboço), então é recriada.
DROP TABLE IF EXISTS fishing_closures;

CREATE TABLE fishing_closures (
    id               bigserial PRIMARY KEY,
    species          text NOT NULL,
    scientific_name  text,
    region           text,
    environment      text NOT NULL CHECK (environment IN ('marine', 'continental')),
    -- 'MM-DD'. Se o fim vier antes do início, o período atravessa a virada do ano.
    prohibition_start text NOT NULL CHECK (prohibition_start ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
    prohibition_end   text NOT NULL CHECK (prohibition_end   ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
    -- NULL = vale todos os anos; preenchido = só para o período que começa nesse ano.
    year             integer CHECK (year BETWEEN 2000 AND 2100),
    fishing_type     text,          -- artesanal, industrial ou ambos (texto da fonte)
    legal_reference  text NOT NULL,
    source_url       text,
    source_type      text NOT NULL DEFAULT 'official' CHECK (source_type IN ('official', 'derived')),
    last_verified_at date,
    notes            text,
    ingested_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX fishing_closures_key_idx
    ON fishing_closures (legal_reference, species, prohibition_start, prohibition_end, COALESCE(year, 0));
CREATE INDEX fishing_closures_species_idx ON fishing_closures (lower(species));

-- Onde o período vale. ibge_code NULL = UF inteira (ou litoral inteiro, com uf NULL não permitido).
CREATE TABLE fishing_closure_areas (
    closure_id    bigint NOT NULL REFERENCES fishing_closures (id) ON DELETE CASCADE,
    uf            text NOT NULL,
    ibge_code     text NOT NULL DEFAULT '',
    municipality  text,
    PRIMARY KEY (closure_id, uf, ibge_code)
);
CREATE INDEX fishing_closure_areas_lookup_idx ON fishing_closure_areas (uf, ibge_code);
