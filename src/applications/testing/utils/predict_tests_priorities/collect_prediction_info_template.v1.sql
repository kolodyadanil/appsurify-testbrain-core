-- CREATE OR REPLACE FUNCTION assign_test_result_type
-- (
--     td testing_defect,
--     tdcabc testing_defect_caused_by_commits default null,
--     tdclbc testing_defect_closed_by_commits default null
-- )
--     RETURNS int AS $$
-- BEGIN
--     IF (tdcabc IS NOT NULL OR tdclbc IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN
--         RETURN 1;
--     ELSE
--         RETURN 0;
--     END IF;
-- END
-- $$ LANGUAGE 'plpgsql' IMMUTABLE;
--
--
-- CREATE OR REPLACE FUNCTION array_coalesce
-- (
--     arr text[],
--     dflt text[] DEFAULT ARRAY ['']
-- )
--     RETURNS text[] AS $$
-- BEGIN
--     IF cardinality(arr) > 0 THEN
--         RETURN arr;
--     ELSE
--         RETURN dflt;
--     END IF;
-- END
-- $$ LANGUAGE plpgsql;
--
--
-- CREATE OR REPLACE FUNCTION normalize_filepath_string
-- (
--     str text
-- )
--     RETURNS text AS $$
-- BEGIN
--     RETURN rtrim(ltrim(regexp_replace(lower(replace(str, ' ', '_')), E'[\\n\\r]+', '', 'g')));
-- END;
-- $$ LANGUAGE plpgsql;
--
--
-- CREATE OR REPLACE FUNCTION full_trim
-- (
--     str text
-- )
--     RETURNS text AS $$
-- BEGIN
--     RETURN rtrim(ltrim(regexp_replace(str, E'[\\n\\r]+', '', 'g')));
-- END;
-- $$ LANGUAGE plpgsql;
--
--
-- CREATE OR REPLACE FUNCTION make_tsvector
-- (
--     txt TEXT
-- )
--     RETURNS tsvector AS $$
-- BEGIN
--     RETURN to_tsvector(
--         regexp_replace(
--             regexp_replace(txt, '[^a-zA-Z0-9]+', ' ', 'g')
--             , '([a-z])([A-Z])', '\1 \2', 'g')
--         );
-- END
-- $$ LANGUAGE 'plpgsql' IMMUTABLE;
--
--
-- CREATE INDEX IF NOT EXISTS vcs_file_filename_tsv_func_idx ON vcs_file
--     USING GIN(make_tsvector(vcs_file.filename));
--
-- CREATE INDEX IF NOT EXISTS vcs_area_name_tsv_func_idx ON vcs_area
--     USING GIN(make_tsvector(vcs_area.name));
--
-- CREATE INDEX IF NOT EXISTS testing_test_name_tsv_func_idx ON testing_test
--     USING GIN(make_tsvector(testing_test.name));
--
-- CREATE INDEX IF NOT EXISTS testing_test_class_name_tsv_func_idx ON testing_test
--     USING GIN(make_tsvector(testing_test.class_name));
--
-- CREATE INDEX IF NOT EXISTS testing_test_complex_tsv_func_idx ON testing_test
--     USING GIN(make_tsvector(testing_test.name || ' ' || testing_test.class_name));
--
--
-- CREATE OR REPLACE FUNCTION make_tsquery
-- (
--     txt TEXT,
--     search_operator VARCHAR default '|'
-- )
--     RETURNS tsquery AS $$
-- BEGIN
--     txt :=
--         array_to_string(
--             (SELECT array_agg(lexeme ORDER BY positions)
--             FROM unnest(make_tsvector(txt)) arr),
--             search_operator);
--     RETURN to_tsquery(txt);
-- END
-- $$ LANGUAGE 'plpgsql' IMMUTABLE;
--
--
-- CREATE OR REPLACE FUNCTION test_similarnamed
-- (
--     project int,
--     test_name text,
--     test_class_name text
-- ) RETURNS text[] AS $$
-- BEGIN
--     RETURN array(
--         SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
--         FROM vcs_file
--         WHERE project_id = project AND vcs_file.lft = (vcs_file.rght - 1)
--         AND make_tsvector(vcs_file.filename) @@ make_tsquery(test_name || ' ' || test_class_name)
--         -- AND (make_tsvector(vcs_file.filename) @@ make_tsquery(test_name)
--         -- AND make_tsvector(vcs_file.filename) @@ make_tsquery(test_class_name)
--         -- AND (make_tsvector(vcs_file.filename) @@ make_tsquery(test_name) OR make_tsvector(vcs_file.filename) @@ make_tsquery(test_class_name))
--     );
-- END
-- $$ LANGUAGE plpgsql IMMUTABLE;
--
--
-- CREATE OR REPLACE FUNCTION test_area_similarnamed
-- (
--     project int,
--     area_name text
-- ) RETURNS text[] AS $$
-- BEGIN
--     RETURN array(
--         SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
--         FROM vcs_file
--         WHERE project_id = project AND vcs_file.lft = (vcs_file.rght - 1)
--         AND make_tsvector(vcs_file.filename) @@ make_tsquery(area_name)
--     );
-- END
-- $$ LANGUAGE plpgsql IMMUTABLE;

SELECT
    DISTINCT ttrr.test_id AS test_id,
    array_remove(array_agg(DISTINCT full_trim(tt.name)), NULL) AS test_names,
    array_remove(array_agg(DISTINCT tt.class_name), NULL) AS test_classes_names,
    array_remove(array_agg(DISTINCT lower(va.name)), NULL) AS test_areas,
    array_remove(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas,
    array_remove(array_agg(DISTINCT normalize_filepath_string(full_trim(vf.full_filename))), NULL) AS test_associated_files,
    array_remove(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas,

    -- test_similarnamed(tt.project_id, string_agg(tt.name, ' '), string_agg(tt.class_name, ' ')) AS test_similarnamed,
    ARRAY[]::text[] AS test_similarnamed,
    array_remove(test_area_similarnamed(tt.project_id, string_agg(va.name, ' ')), NULL) AS test_area_similarnamed,
    vc.rework AS commit_rework,
    vc.riskiness::numeric::integer * 100 AS commit_riskiness,
    array_remove(array_agg(DISTINCT normalize_filepath_string(full_trim(va4.name))), NULL) AS commit_areas,
    array_remove(array_agg(DISTINCT normalize_filepath_string(full_trim(vf2.full_filename))), NULL) AS commit_files,
    array_remove(array_agg(DISTINCT normalize_filepath_string(full_trim(vf3.full_filename))), NULL) AS defect_closed_by_caused_by_commits_files,
    array_remove(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_closed_by_caused_by_commits_areas,
    array_remove(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_closed_by_caused_by_commits_dependent_areas,
    array_remove(array(SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
           WHERE tdclbc.commit_id = vca.commit_id
           INTERSECT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
           WHERE tdcabc.commit_id = vca.commit_id), NULL) AS defect_closed_by_caused_by_intersection_areas,
    array_remove(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE tdclbc.commit_id = vf.commit_id
           INTERSECT
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE tdcabc.commit_id = vf.commit_id
           ), NULL) AS defect_closed_by_caused_by_intersection_files

FROM testing_testrunresult ttrr
    INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
    INNER JOIN testing_test tt on ttrr.test_id = tt.id
    INNER JOIN vcs_area va ON tt.area_id = va.id
    LEFT OUTER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
    LEFT OUTER JOIN testing_defect_caused_by_commits tdcabc on td.id = tdcabc.defect_id
    LEFT OUTER JOIN testing_defect_closed_by_commits tdclbc on td.id = tdclbc.defect_id
    LEFT OUTER JOIN testing_test_associated_areas ttaa2 on va.id = ttaa2.area_id
    LEFT OUTER JOIN vcs_area va2 on ttaa2.area_id = va2.id
    LEFT OUTER JOIN testing_test_associated_files ttaf on tt.id = ttaf.test_id
    LEFT OUTER JOIN vcs_file vf on ttaf.file_id = vf.id
    LEFT OUTER JOIN vcs_area_dependencies vad on va.id = vad.to_area_id
    LEFT OUTER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
    LEFT OUTER JOIN vcs_area va3 on ttaa3.area_id = va3.id
    LEFT OUTER JOIN vcs_commit_areas vca4 on vc.id = vca4.commit_id
    LEFT OUTER JOIN vcs_area va4 on vca4.area_id = va4.id
    LEFT OUTER JOIN vcs_filechange vfc2 on vc.id = vfc2.commit_id
    LEFT OUTER JOIN vcs_file vf2 on vfc2.file_id = vf2.id

    LEFT OUTER JOIN vcs_filechange vfc3 on tdcabc.commit_id = vfc3.commit_id or tdclbc.commit_id = vfc3.commit_id
    LEFT OUTER JOIN vcs_file vf3 on vf3.id = vfc3.file_id

    LEFT OUTER JOIN vcs_commit_areas vca5 on tdcabc.commit_id = vca5.commit_id or tdclbc.commit_id = vca5.commit_id
    LEFT OUTER JOIN vcs_area va5 on vca5.area_id = va5.id

    LEFT OUTER JOIN vcs_commit_areas vca6 on tdcabc.commit_id = vca6.commit_id OR tdclbc.commit_id = vca6.commit_id
    LEFT OUTER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad.from_area_id
    LEFT OUTER JOIN vcs_area va6 on va6.id = vad6.to_area_id

WHERE
    ttrr.test_id IN {tests_ids} AND vc.id IN {commits_ids}
GROUP BY ttrr.test_id,
         tt.project_id,
         vc.sha,
         vc.rework,
         vc.riskiness,
         tdclbc.commit_id,
         tdcabc.commit_id
;

