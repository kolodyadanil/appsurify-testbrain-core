# -*- coding: utf-8 -*-
from django.db import connection


def create_functions(**kwargs):
    print('  (re)creating license help functions...')
    sql = """
CREATE OR REPLACE FUNCTION round_execution_time
(
    execution_time float
)
    RETURNS int AS $$
BEGIN
    IF execution_time::int = 0 THEN
        RETURN 10;
    ELSE
        RETURN execution_time::int;
    END IF;
END
$$ LANGUAGE 'plpgsql' IMMUTABLE;
    """
    cursor = connection.cursor()
    cursor.execute(sql)
    print('  Done creating license help functions.')
