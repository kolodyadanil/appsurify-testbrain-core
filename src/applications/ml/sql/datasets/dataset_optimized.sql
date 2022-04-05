WITH test_suite_id AS (SELECT 346 AS test_suite_id),
min_date AS (SELECT '2022-02-05 00:00:00'::timestamp - interval '7 days' as min_date),
max_date AS (SELECT '2022-02-05 00:00:00'::timestamp as max_date),
ttrr AS 
(
    SELECT
        tt.project_id,
        vc.sha,
        vc.rework,
        vc.riskiness,
        va.id AS va_id,
        vc.id AS vc_id,
        tt.id AS tt_id,
        td.id AS td_id,
        tt.name as tt_name,
        tt.class_name,
        va.name as va_name,
				td.type as td_type,
				td.close_type as td_close_type
    FROM testing_testrunresult ttrr
        INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
        INNER JOIN testing_test tt on ttrr.test_id = tt.id
        INNER JOIN vcs_area va ON tt.area_id = va.id
        LEFT OUTER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
    WHERE
        ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
),
ttrr_grp AS (
    SELECT
        MAX(CASE WHEN (tdc.defect_id IS NOT NULL) AND ttrr.td_type IN (3,4) AND ttrr.td_close_type IN (1,3) THEN 1 ELSE 0 END) AS test_changed,
        ttrr.project_id,
        ttrr.sha,
        ttrr.rework,
        ttrr.riskiness,
    array_remove(array_agg(DISTINCT full_trim(ttrr.tt_name)), NULL) AS test_names,
    array_remove(array_agg(DISTINCT ttrr.class_name), NULL) AS test_classes_names,
    array_remove(array_agg(DISTINCT lower(ttrr.va_name)), NULL) AS test_areas,

    ARRAY [''] AS test_similarnamed,

    array_remove(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_defect_closed_by_commits tdclbc ON (tdclbc.commit_id = vca.commit_id)
           WHERE tdclbc.defect_id = ttrr.td_id
           INTERSECT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_defect_caused_by_commits tdcabc ON (tdcabc.commit_id = vca.commit_id)
           WHERE tdcabc.defect_id = ttrr.td_id), NULL) AS defect_closed_by_caused_by_intersection_areas,
    array_remove(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_closed_by_commits tdclbc ON (tdclbc.commit_id = vf.commit_id)
           WHERE tdclbc.defect_id = ttrr.td_id
           INTERSECT
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_caused_by_commits tdcabc ON (tdcabc.commit_id = vf.commit_id)
           WHERE tdcabc.defect_id = ttrr.td_id
           ), NULL) AS defect_closed_by_caused_by_intersection_files
FROM ttrr
LEFT JOIN LATERAL (SELECT defect_id, updated FROM testing_defect_caused_by_commits tdcabc WHERE ttrr.td_id = tdcabc.defect_id AND tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
	UNION SELECT
	defect_id, updated FROM testing_defect_closed_by_commits tdclbc WHERE ttrr.td_id = tdclbc.defect_id AND tdclbc.updated > (SELECT min_date FROM min_date) AND tdclbc.updated < (SELECT max_date FROM max_date)) tdc ON TRUE
GROUP BY ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
				 ttrr.td_id),
test_area_similarnamed AS (
SELECT ttrr.project_id,
         ttrr.test_areas,
         array_remove(test_area_similarnamed(ttrr.project_id, array_to_string(ttrr.test_areas, ' ')), NULL) AS test_area_similarnamed
FROM (SELECT project_id, test_areas FROM ttrr_grp GROUP BY project_id, test_areas ORDER BY 1, 2) ttrr
) ,
test_associated_areas AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
array_remove(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_test_associated_areas ttaa2 on ttrr.area_id = ttaa2.area_id
INNER JOIN vcs_area va2 on ttaa2.area_id = va2.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (ttaa2.updated > (SELECT min_date FROM min_date) AND ttaa2.updated < (SELECT max_date FROM max_date)
OR va2.updated > (SELECT min_date FROM min_date) AND va2.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
test_associated_files AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
array_remove(normalize_filepath_string(array_agg(DISTINCT vf.full_filename)), NULL) AS test_associated_files
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_test_associated_files ttaf on ttrr.test_id = ttaf.test_id
INNER JOIN vcs_file vf on ttaf.file_id = vf.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (ttaf.updated > (SELECT min_date FROM min_date) AND ttaf.updated < (SELECT max_date FROM max_date)
OR vf.updated > (SELECT min_date FROM min_date) AND vf.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
test_dependent_areas AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
array_remove(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_area_dependencies vad on ttrr.area_id = vad.to_area_id
INNER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
INNER JOIN vcs_area va3 on ttaa3.area_id = va3.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (vad.updated > (SELECT min_date FROM min_date) AND vad.updated < (SELECT max_date FROM max_date)
OR ttaa3.updated > (SELECT min_date FROM min_date) AND ttaa3.updated < (SELECT max_date FROM max_date)
OR va3.updated > (SELECT min_date FROM min_date) AND va3.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
commit_areas AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
array_remove(normalize_filepath_string(array_agg(DISTINCT va4.name)), NULL) AS commit_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_commit_areas vca4 on ttrr.commit_id = vca4.commit_id
INNER JOIN vcs_area va4 on vca4.area_id = va4.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (vca4.updated > (SELECT min_date FROM min_date) AND vca4.updated < (SELECT max_date FROM max_date)
OR va4.updated > (SELECT min_date FROM min_date) AND va4.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
commit_files AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf2.full_filename)), NULL) AS commit_files
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_filechange vfc2 on ttrr.commit_id = vfc2.commit_id
INNER JOIN vcs_file vf2 on vfc2.file_id = vf2.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (vfc2.updated > (SELECT min_date FROM min_date) AND vfc2.updated < (SELECT max_date FROM max_date)
OR vf2.updated > (SELECT min_date FROM min_date) AND vf2.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
defect_closed_by_caused_by_commits_files AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf3.full_filename)), NULL) AS defect_closed_by_caused_by_commits_files
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN LATERAL (SELECT commit_id, updated FROM testing_defect_caused_by_commits tdcabc WHERE td.id = tdcabc.defect_id
	UNION SELECT
	commit_id, updated FROM testing_defect_closed_by_commits tdclbc WHERE td.id = tdclbc.defect_id) tdc ON TRUE
INNER JOIN vcs_filechange vfc3 on tdc.commit_id = vfc3.commit_id
INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (
tdc.updated > (SELECT min_date FROM min_date) AND tdc.updated < (SELECT max_date FROM max_date)
OR vfc3.updated > (SELECT min_date FROM min_date) AND vfc3.updated < (SELECT max_date FROM max_date)
OR vf3.updated > (SELECT min_date FROM min_date) AND vf3.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
defect_closed_by_caused_by_commits_areas AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
    array_remove(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_closed_by_caused_by_commits_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN LATERAL (SELECT commit_id, updated FROM testing_defect_caused_by_commits tdcabc WHERE td.id = tdcabc.defect_id
	UNION SELECT
	commit_id, updated FROM testing_defect_closed_by_commits tdclbc WHERE td.id = tdclbc.defect_id) tdc ON TRUE
INNER JOIN vcs_commit_areas vca5 on tdc.commit_id = vca5.commit_id
INNER JOIN vcs_area va5 on vca5.area_id = va5.id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (tdc.updated > (SELECT min_date FROM min_date) AND tdc.updated < (SELECT max_date FROM max_date)
OR vca5.updated > (SELECT min_date FROM min_date) AND vca5.updated < (SELECT max_date FROM max_date)
OR va5.updated > (SELECT min_date FROM min_date) AND va5.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness),
defect_closed_by_caused_by_commits_dependent_areas AS (
SELECT tt.project_id,
vc.sha,
vc.rework,
vc.riskiness,
    array_remove(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_closed_by_caused_by_commits_dependent_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN LATERAL (SELECT commit_id, updated FROM testing_defect_caused_by_commits tdcabc WHERE td.id = tdcabc.defect_id
	UNION SELECT
	commit_id, updated FROM testing_defect_closed_by_commits tdclbc WHERE td.id = tdclbc.defect_id) tdc ON TRUE
INNER JOIN vcs_commit_areas vca6 on tdc.commit_id = vca6.commit_id
INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
WHERE ttrr.test_suite_id = (SELECT test_suite_id FROM test_suite_id)
AND (
tdc.updated > (SELECT min_date FROM min_date) AND tdc.updated < (SELECT max_date FROM max_date)
OR vca6.updated > (SELECT min_date FROM min_date) AND vca6.updated < (SELECT max_date FROM max_date)
OR vad6.updated > (SELECT min_date FROM min_date) AND vad6.updated < (SELECT max_date FROM max_date)
OR va6.updated > (SELECT min_date FROM min_date) AND va6.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
vc.sha,
vc.rework,
vc.riskiness)

SELECT COALESCE(ttrr.test_changed, 0) AS test_changed,
ttrr.test_names,
ttrr.test_classes_names,
ttrr.test_areas,
taa.test_associated_areas,
taf.test_associated_files,
tda.test_dependent_areas,
ttrr.test_similarnamed,
tasn.test_area_similarnamed,
ttrr.rework AS commit_rework,
ttrr.riskiness::numeric::integer * 100 AS commit_riskiness,
ca.commit_areas,
cf.commit_files,
dccf.defect_closed_by_caused_by_commits_files,
dcca.defect_closed_by_caused_by_commits_areas,
dccda.defect_closed_by_caused_by_commits_dependent_areas,
ttrr.defect_closed_by_caused_by_intersection_areas,
ttrr.defect_closed_by_caused_by_intersection_files
FROM ttrr_grp ttrr
FULL OUTER JOIN test_area_similarnamed tasn ON ttrr.project_id = tasn.project_id
FULL OUTER JOIN test_associated_areas taa ON ttrr.project_id = taa.project_id
	and ttrr.sha = taa.sha
	and ttrr.rework = taa.rework
	and ttrr.riskiness = taa.riskiness
FULL OUTER JOIN test_associated_files taf ON ttrr.project_id = taf.project_id
	and ttrr.sha = taf.sha
	and ttrr.rework = taf.rework
	and ttrr.riskiness = taf.riskiness
FULL OUTER JOIN test_dependent_areas tda ON ttrr.project_id = tda.project_id
	and ttrr.sha = tda.sha
	and ttrr.rework = tda.rework
	and ttrr.riskiness = tda.riskiness
FULL OUTER JOIN commit_areas ca ON ttrr.project_id = ca.project_id
	and ttrr.sha = ca.sha
	and ttrr.rework = ca.rework
	and ttrr.riskiness = ca.riskiness
FULL OUTER JOIN commit_files cf ON ttrr.project_id = cf.project_id
	and ttrr.sha = cf.sha
	and ttrr.rework = cf.rework
	and ttrr.riskiness = cf.riskiness
FULL OUTER JOIN defect_closed_by_caused_by_commits_files dccf ON ttrr.project_id = dccf.project_id
	and ttrr.sha = dccf.sha
	and ttrr.rework = dccf.rework
	and ttrr.riskiness = dccf.riskiness
FULL OUTER JOIN defect_closed_by_caused_by_commits_areas dcca ON ttrr.project_id = dcca.project_id
	and ttrr.sha = dcca.sha
	and ttrr.rework = dcca.rework
	and ttrr.riskiness = dcca.riskiness
FULL OUTER JOIN defect_closed_by_caused_by_commits_dependent_areas dccda ON ttrr.project_id = dccda.project_id
	and ttrr.sha = dccda.sha
	and ttrr.rework = dccda.rework
	and ttrr.riskiness = dccda.riskiness