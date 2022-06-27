WITH
min_date AS (SELECT '{min_date}'::timestamp as min_date),
max_date AS (SELECT '{max_date}'::timestamp as max_date)
SELECT test_id,
MAX(max_test_changed) AS max_test_changed,
MIN(min_test_changed) AS min_test_changed
FROM (
	SELECT
			ttrr.test_id,
			ttrr.test_run_id,
					COALESCE(MAX(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0) AS max_test_changed,
					COALESCE(MIN(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0) AS min_test_changed
		FROM testing_testrunresult ttrr
		LEFT JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
		INNER JOIN testing_testrun ttr ON ttrr.test_run_id = ttr.id
		LEFT JOIN testing_testrunresult prev_ttrr ON ttr.previous_test_run_id = prev_ttrr.test_run_id AND ttrr.test_id = prev_ttrr.test_id
		LEFT JOIN (SELECT defect_id, updated FROM testing_defect_caused_by_commits tdcabc
			UNION
			SELECT defect_id, updated FROM testing_defect_closed_by_commits tdclbc
			) tdc ON td.id = tdc.defect_id
	WHERE
		ttrr.test_suite_id = {test_suite_id}
		AND ttrr.status IS DISTINCT FROM prev_ttrr.status
		AND (ttrr.updated > (SELECT min_date FROM min_date) AND ttrr.updated < (SELECT max_date FROM max_date)
		OR td.updated > (SELECT min_date FROM min_date) AND td.updated < (SELECT max_date FROM max_date)
		OR tdc.updated > (SELECT min_date FROM min_date) AND tdc.updated < (SELECT max_date FROM max_date))
	GROUP BY ttrr.test_id, ttrr.test_run_id
	HAVING (MIN(CASE WHEN ttrr.status = 'pass' THEN 1 ELSE 0 END) = 0)
) t
GROUP BY t.test_id
HAVING MAX(max_test_changed) <> MIN(min_test_changed)