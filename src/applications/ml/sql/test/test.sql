SELECT
				ttrr.test_id,
        COALESCE(MAX(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0) AS max_test_changed,
        COALESCE(MIN(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0) AS min_test_changed
	FROM testing_testrunresult ttrr
	LEFT JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
LEFT JOIN (SELECT defect_id FROM testing_defect_caused_by_commits tdcabc
	UNION
	SELECT defect_id FROM testing_defect_closed_by_commits tdclbc
	) tdc ON td.id = tdc.defect_id
WHERE
	ttrr.test_suite_id = {test_suite_id}
GROUP BY ttrr.test_id
HAVING COALESCE(MAX(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0) <>
        COALESCE(MIN(CASE WHEN (tdc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END), 0)