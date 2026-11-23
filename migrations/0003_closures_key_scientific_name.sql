-- Um defeso por espécie: o nome científico passa a fazer parte da chave única.
-- Antes, espécies com o mesmo nome popular na mesma norma e período (bagres, robalos, camarão-rosa)
-- caíam na mesma linha. scientific_name NULL e '' são tratados como iguais.
DROP INDEX IF EXISTS fishing_closures_key_idx;
CREATE UNIQUE INDEX fishing_closures_key_idx
    ON fishing_closures (legal_reference, species, COALESCE(scientific_name, ''),
                         prohibition_start, prohibition_end, COALESCE(year, 0));
