CREATE MATERIALIZED VIEW mv_test_count_by_type_{project_id} AS
WITH test_run_execution_time AS (
    SELECT
        testing_testrunresult.test_run_id,
        SUM(testing_testrunresult.execution_time) as execution_time
    FROM testing_testrunresult
    WHERE "testing_testrunresult"."project_id" = 426
    GROUP BY 1
), test_run_statistic AS (
SELECT test_run_id,
    COUNT(*) AS tests_count,
    COUNT(CASE WHEN status = 'passed' THEN 1 END) AS passed_tests_count,
    COUNT(CASE WHEN status = 'skipped' THEN 1 END) AS skipped_tests_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_tests_count,
    COUNT(CASE WHEN status = 'broken' THEN 1 END) AS broken_tests_count,
    COUNT(CASE WHEN status IN ('pending', 'skipped', 'not_run') THEN 1 END) AS not_run_tests_count
FROM (
	SELECT DISTINCT ON (test_run_id, test_id)
	test_run_id,
	test_id,
	status
	FROM testing_testrunresult
	ORDER BY test_run_id,
	test_id,
	test_run_start_date DESC
) t
GROUP BY test_run_id)
SELECT test_run_execution_time.test_run_id,
    test_run_statistic.tests_count,
    test_run_statistic.passed_tests_count,
    test_run_statistic.skipped_tests_count,
    test_run_statistic.failed_tests_count,
    test_run_statistic.broken_tests_count,
    test_run_statistic.not_run_tests_count,
    test_run_execution_time.execution_time
FROM test_run_execution_time
LEFT JOIN test_run_statistic ON test_run_execution_time.test_run_id = test_run_statistic.test_run_id;

CREATE INDEX ON mv_test_count_by_type(test_run_id);


REFRESH MATERIALIZED VIEW mv_test_count_by_type;