WITH created_defect_count AS (
SELECT testing_testrun.id,
COUNT(*) AS created_defects__count
FROM testing_testrun
INNER JOIN testing_defect ON testing_testrun.id = testing_defect.created_by_test_run_id
WHERE "testing_testrun"."project_id" = %(project_id)s
GROUP BY testing_testrun.id
), founded_defect_count AS (
SELECT testing_testrun.id,
COUNT(*) AS founded_defects__flaky_failure__count
FROM testing_defect
INNER JOIN testing_testrunresult ON "testing_testrunresult"."id" = "testing_defect"."created_by_test_run_result_id"
INNER JOIN testing_testrun ON testing_testrunresult.test_run_id = testing_testrun.id
WHERE testing_defect."type" IN (2, 4, 1)
AND "testing_testrun"."project_id" = %(project_id)s
GROUP BY testing_testrun.id
)
SELECT "testing_testrun"."project_id",
       "project_project"."name" as "project_name",
       "testing_testrun"."test_suite_id",
       "testing_testsuite"."name" as "test_suite_name",
       DATE_TRUNC('second', "testing_testrun"."start_date" AT TIME ZONE 'UTC') AS "start_date",
        COALESCE(mv_test_count_by_type.tests__count, 0) AS tests__count,
        COALESCE(created_defect_count.created_defects__count, 0) AS created_defects__count,
        COALESCE(founded_defect_count.founded_defects__flaky_failure__count, 0) AS founded_defects__flaky_failure__count,
        COALESCE(mv_test_count_by_type.passed_tests__count, 0) AS passed_tests__count,
        COALESCE(mv_test_count_by_type.skipped_tests__count, 0) AS skipped_tests__count,
        COALESCE(mv_test_count_by_type.failed_tests__count, 0) AS failed_tests__count,
        COALESCE(mv_test_count_by_type.broken_tests__count, 0) AS broken_tests__count,
        COALESCE(mv_test_count_by_type.not_run_tests__count, 0) AS not_run_tests__count,
        COALESCE(mv_test_count_by_type."execution_time", 0) AS execution_time,
         (SELECT COALESCE(SUM("execution_time"), 0) FROM "testing_testrunresult" WHERE "test_run_id" = "testing_testrun"."previous_test_run_id") AS "previous_execution_time",
       "testing_testrun"."id",
       "testing_testrun"."name",
       DATE_TRUNC('second', "testing_testrun"."end_date" AT TIME ZONE 'UTC') AS "end_date"
FROM testing_testrun
INNER JOIN "project_project" ON ("testing_testrun"."project_id" = "project_project"."id")
INNER JOIN "testing_testsuite" ON ("testing_testrun"."test_suite_id" = "testing_testsuite"."id")
LEFT OUTER JOIN mv_test_count_by_type ON testing_testrun.id = mv_test_count_by_type.test_run_id
LEFT OUTER JOIN created_defect_count ON testing_testrun.id = created_defect_count.id
LEFT OUTER JOIN founded_defect_count ON testing_testrun.id = founded_defect_count.id
WHERE "project_project"."organization_id" = %(organization_id)s
       AND"testing_testrun"."project_id" = %(project_id)s
       AND NOT "testing_testrun"."is_local"
GROUP BY "testing_testrun"."id",
         DATE_TRUNC('second', "testing_testrun"."start_date" AT TIME ZONE 'UTC'),
         "testing_testrun"."name",
         "testing_testrun"."type",
         DATE_TRUNC('second', "testing_testrun"."end_date" AT TIME ZONE 'UTC'),
         "testing_testrun"."project_id",
         "project_project"."name",
         "testing_testrun"."test_suite_id",
         "testing_testsuite"."name",
         "testing_testrun"."previous_test_run_id",
         "mv_test_count_by_type"."tests__count",
         "created_defect_count"."created_defects__count",
         "founded_defect_count"."founded_defects__flaky_failure__count",
         "mv_test_count_by_type"."passed_tests__count",
         "mv_test_count_by_type"."skipped_tests__count",
         "mv_test_count_by_type"."failed_tests__count",
         "mv_test_count_by_type"."broken_tests__count",
         "mv_test_count_by_type"."not_run_tests__count",
         mv_test_count_by_type."execution_time"
ORDER BY "start_date" DESC