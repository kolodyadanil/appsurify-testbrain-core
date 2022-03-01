# -*- coding: utf-8 -*-

from django.db import connection


def create_functions(**kwargs):
    print('  (re)creating testing help functions...')
    sql = """
CREATE OR REPLACE FUNCTION assign_test_result_type
(
    td testing_defect,
    tdcabc testing_defect_caused_by_commits default null,
    tdclbc testing_defect_closed_by_commits default null
)
    RETURNS int AS $$
BEGIN
    IF (tdcabc IS NOT NULL OR tdclbc IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN
        RETURN 1;
    ELSE
        RETURN 0;
    END IF;
END
$$ LANGUAGE 'plpgsql' IMMUTABLE;


CREATE OR REPLACE FUNCTION array_coalesce
(
    arr text[],
    dflt text[] DEFAULT ARRAY ['']
)
    RETURNS text[] AS $$
BEGIN
    IF cardinality(arr) > 0 THEN
        RETURN arr;
    ELSE
        RETURN dflt;
    END IF;
END
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION normalize_filepath_string
(
    str text
)
    RETURNS text AS $$
BEGIN
    RETURN rtrim(ltrim(regexp_replace(lower(replace(str, ' ', '_')), E'[\\n\\r]+', '', 'g')));
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION normalize_filepath_string(arr text[])
    RETURNS text[]
    LANGUAGE plpgsql
AS $function$
DECLARE
    i integer;
    arr_out text[];
BEGIN
    FOR i IN 1 .. array_upper(arr, 1) LOOP
        arr_out[i] := rtrim(ltrim(regexp_replace(lower(replace(arr[i], ' ', '_')), E'[\n\r]+', '', 'g')));
    END LOOP;
    
    RETURN arr_out;
END;
$function$;


CREATE OR REPLACE FUNCTION full_trim
(
    str text
)
    RETURNS text AS $$
BEGIN
    RETURN rtrim(ltrim(regexp_replace(str, E'[\\n\\r]+', '', 'g')));
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION make_tsvector
(
    txt TEXT
)
    RETURNS tsvector AS $$
BEGIN
    RETURN to_tsvector(
        regexp_replace(
            regexp_replace(txt, '[^a-zA-Z0-9]+', ' ', 'g')
            , '([a-z])([A-Z])', '\1 \2', 'g')
        );
END
$$ LANGUAGE 'plpgsql' IMMUTABLE;


CREATE INDEX IF NOT EXISTS vcs_file_filename_tsv_func_idx ON vcs_file
    USING GIN(make_tsvector(vcs_file.filename));

CREATE INDEX IF NOT EXISTS vcs_area_name_tsv_func_idx ON vcs_area
    USING GIN(make_tsvector(vcs_area.name));

CREATE INDEX IF NOT EXISTS testing_test_name_tsv_func_idx ON testing_test
    USING GIN(make_tsvector(testing_test.name));

CREATE INDEX IF NOT EXISTS testing_test_class_name_tsv_func_idx ON testing_test
    USING GIN(make_tsvector(testing_test.class_name));

CREATE INDEX IF NOT EXISTS testing_test_complex_tsv_func_idx ON testing_test
    USING GIN(make_tsvector(testing_test.name || ' ' || testing_test.class_name));


CREATE OR REPLACE FUNCTION make_tsquery
(
    txt TEXT,
    search_operator VARCHAR default '|'
)
    RETURNS tsquery AS $$
BEGIN
    txt :=
        array_to_string(
            (SELECT array_agg(lexeme ORDER BY positions)
            FROM unnest(make_tsvector(txt)) arr),
            search_operator);
    RETURN to_tsquery(txt);
END
$$ LANGUAGE 'plpgsql' IMMUTABLE;


CREATE OR REPLACE FUNCTION test_similarnamed
(
    project int,
    test_name text,
    test_class_name text
) RETURNS text[] AS $$
BEGIN
    RETURN array(
        SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
        FROM vcs_file
        WHERE project_id = project AND vcs_file.lft = (vcs_file.rght - 1)
        AND make_tsvector(vcs_file.filename) @@ make_tsquery(test_name || ' ' || test_class_name)
        -- AND (make_tsvector(vcs_file.filename) @@ make_tsquery(test_name)
        -- AND make_tsvector(vcs_file.filename) @@ make_tsquery(test_class_name)
        -- AND (make_tsvector(vcs_file.filename) @@ make_tsquery(test_name) OR make_tsvector(vcs_file.filename) @@ make_tsquery(test_class_name))
    );
END
$$ LANGUAGE plpgsql IMMUTABLE;


CREATE OR REPLACE FUNCTION test_area_similarnamed
(
    project int,
    area_name text
) RETURNS text[] AS $$
BEGIN
    RETURN array(
        SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
        FROM vcs_file
        WHERE project_id = project AND vcs_file.lft = (vcs_file.rght - 1)
        AND make_tsvector(vcs_file.filename) @@ make_tsquery(area_name)
    );
END
$$ LANGUAGE plpgsql IMMUTABLE;
    """
    cursor = connection.cursor()
    cursor.execute(sql)
    print('  Done creating testing help functions.')
