WITH test_suite_id AS (SELECT {test_suite_id} AS test_suite_id, {test_id} as test_id),
min_date AS (SELECT '{min_date}'::timestamp as min_date),
max_date AS (SELECT '{max_date}'::timestamp as max_date),

ttrr AS
(
    SELECT
        tt.project_id,
        tt.name as test_name,
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
				td.close_type as td_close_type,
				ttrr.test_run_id,
				ttrr.status,
				ttr.previous_test_run_id
    FROM testing_testrunresult ttrr
        INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
        INNER JOIN testing_test tt on ttrr.test_id = tt.id
        INNER JOIN vcs_area va ON tt.area_id = va.id
        LEFT OUTER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
				INNER JOIN testing_testrun ttr ON ttrr.test_run_id = ttr.id
				LEFT OUTER JOIN testing_testrunresult prev_ttrr ON ttr.previous_test_run_id = prev_ttrr.test_run_id AND ttrr.test_id = prev_ttrr.test_id
    WHERE
        (ttrr.test_suite_id, ttrr.test_id) IN (SELECT test_suite_id, test_id FROM test_suite_id)
				AND ttrr.status IS DISTINCT FROM prev_ttrr.status
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17
),
ttrr_grp AS (
    SELECT ttrr.test_run_id,
				ttrr.tt_id,
				MAX(CASE WHEN (tdc.defect_id IS NOT NULL) AND ttrr.td_type IN (3,4) AND ttrr.td_close_type IN (1,3) THEN 1 ELSE 0 END) AS test_changed,
        ttrr.project_id,
        ttrr.test_name,
        ttrr.sha,
        ttrr.rework,
        ttrr.riskiness,
    array_cleanup(array_agg(DISTINCT full_trim(ttrr.tt_name)), NULL) AS test_names,
    array_cleanup(array_agg(DISTINCT ttrr.class_name), NULL) AS test_classes_names,
    array_cleanup(array_agg(DISTINCT lower(ttrr.va_name)), NULL) AS test_areas,

    NULL AS test_similarnamed,

    COALESCE(array_cleanup(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_defect_closed_by_commits tdclbc ON (tdclbc.commit_id = vca.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdclbc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id
           INTERSECT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_defect_caused_by_commits tdcabc ON (tdcabc.commit_id = vca.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdcabc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id), NULL),
					 array_cleanup(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
           WHERE ttr.id = ttrr.test_run_id
           EXCEPT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
           WHERE ttr.id = ttrr.previous_test_run_id), NULL))
		AS defect_closed_by_caused_by_intersection_areas,
    COALESCE(array_cleanup(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_closed_by_commits tdclbc ON (tdclbc.commit_id = vf.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdclbc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id
           INTERSECT
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_caused_by_commits tdcabc ON (tdcabc.commit_id = vf.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdcabc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id
           ), NULL),
					 array_cleanup(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
           WHERE ttr.id = ttrr.test_run_id
           EXCEPT
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
           WHERE ttr.id = ttrr.previous_test_run_id), NULL)) AS defect_closed_by_caused_by_intersection_files,
    COALESCE(array_cleanup(array(
           SELECT DISTINCT normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/'))))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_closed_by_commits tdclbc ON (tdclbc.commit_id = vf.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdclbc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id
           INTERSECT
           SELECT DISTINCT normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/'))))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_defect_caused_by_commits tdcabc ON (tdcabc.commit_id = vf.commit_id)
							 INNER JOIN testing_defect_associated_tests tdat ON tdcabc.defect_id = tdat.defect_id
           WHERE tdat.test_id = ttrr.tt_id
           ), NULL),
					 array_cleanup(array(
           SELECT DISTINCT normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/'))))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
           WHERE ttr.id = ttrr.test_run_id
           EXCEPT
           SELECT DISTINCT normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/'))))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
           WHERE ttr.id = ttrr.previous_test_run_id), NULL)) AS defect_closed_by_caused_by_intersection_folders,
    COALESCE(array_cleanup(array(
           SELECT DISTINCT normalize_filepath_string(full_trim(va6.name))
           FROM testing_defect_closed_by_commits tdclbc
               INNER JOIN testing_defect_associated_tests tdat ON tdclbc.defect_id = tdat.defect_id
               INNER JOIN vcs_commit_areas vca6 on tdclbc.commit_id = vca6.commit_id
               INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
               INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
           WHERE tdat.test_id = ttrr.tt_id
           INTERSECT
           SELECT DISTINCT normalize_filepath_string(full_trim(va6.name))
           FROM testing_defect_caused_by_commits tdcabc
               INNER JOIN testing_defect_associated_tests tdat ON tdcabc.defect_id = tdat.defect_id
               INNER JOIN vcs_commit_areas vca6 on tdcabc.commit_id = vca6.commit_id
               INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
               INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
           WHERE tdat.test_id = ttrr.tt_id
           ), NULL),
					 array_cleanup(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_area_dependencies vad on vcs_area.id = vad.to_area_id
               INNER JOIN vcs_commit_areas vca ON (vad.from_area_id = vca.area_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
           WHERE ttr.id = ttrr.test_run_id
           EXCEPT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_area_dependencies vad on vcs_area.id = vad.to_area_id
               INNER JOIN vcs_commit_areas vca ON (vad.from_area_id = vca.area_id)
               INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
           WHERE ttr.id = ttrr.previous_test_run_id), NULL)) AS defect_closed_by_caused_by_intersection_dependent_areas
FROM ttrr
LEFT JOIN LATERAL (SELECT defect_id, updated FROM testing_defect_caused_by_commits tdcabc WHERE ttrr.td_id = tdcabc.defect_id AND tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
	UNION SELECT
	defect_id, updated FROM testing_defect_closed_by_commits tdclbc WHERE ttrr.td_id = tdclbc.defect_id AND tdclbc.updated > (SELECT min_date FROM min_date) AND tdclbc.updated < (SELECT max_date FROM max_date)) tdc ON TRUE
GROUP BY ttrr.test_run_id, ttrr.tt_id, ttrr.previous_test_run_id, ttrr.project_id,
         ttrr.test_name,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness
HAVING(MIN(CASE WHEN ttrr.status = 'pass' THEN 1 ELSE 0 END) = 0)
),
test_area_similarnamed AS (
SELECT ttrr.project_id,
         ttrr.test_areas,
         array_cleanup(test_area_similarnamed(ttrr.project_id, array_to_string(ttrr.test_areas, ' ')), NULL) AS test_area_similarnamed
FROM (SELECT project_id, test_areas FROM ttrr_grp GROUP BY project_id, test_areas ORDER BY 1, 2) ttrr
),
test_associated_areas AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
array_cleanup(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_test_associated_areas ttaa2 on ttrr.va_id = ttaa2.area_id
INNER JOIN vcs_area va2 on ttaa2.area_id = va2.id
WHERE (ttaa2.updated > (SELECT min_date FROM min_date) AND ttaa2.updated < (SELECT max_date FROM max_date)
OR va2.updated > (SELECT min_date FROM min_date) AND va2.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
test_associated_files AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf.full_filename)), NULL) AS test_associated_files
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_test_associated_files ttaf on ttrr.tt_id = ttaf.test_id
INNER JOIN vcs_file vf on ttaf.file_id = vf.id
WHERE (ttaf.updated > (SELECT min_date FROM min_date) AND ttaf.updated < (SELECT max_date FROM max_date)
OR vf.updated > (SELECT min_date FROM min_date) AND vf.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
test_dependent_areas AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
array_cleanup(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN vcs_area_dependencies vad on ttrr.va_id = vad.to_area_id
INNER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
INNER JOIN vcs_area va3 on ttaa3.area_id = va3.id
WHERE (vad.updated > (SELECT min_date FROM min_date) AND vad.updated < (SELECT max_date FROM max_date)
OR ttaa3.updated > (SELECT min_date FROM min_date) AND ttaa3.updated < (SELECT max_date FROM max_date)
OR va3.updated > (SELECT min_date FROM min_date) AND va3.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
commit_areas AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
array_cleanup(normalize_filepath_string(array_agg(DISTINCT va4.name)), NULL) AS commit_areas
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN vcs_commit_areas vca4 on ttrr.vc_id = vca4.commit_id
INNER JOIN vcs_area va4 on vca4.area_id = va4.id
WHERE (vca4.updated > (SELECT min_date FROM min_date) AND vca4.updated < (SELECT max_date FROM max_date)
OR va4.updated > (SELECT min_date FROM min_date) AND va4.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
commit_files AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
    array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf2.full_filename)), NULL) AS commit_files
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN vcs_filechange vfc2 on ttrr.vc_id = vfc2.commit_id
INNER JOIN vcs_file vf2 on vfc2.file_id = vf2.id
WHERE (vfc2.updated > (SELECT min_date FROM min_date) AND vfc2.updated < (SELECT max_date FROM max_date)
OR vf2.updated > (SELECT min_date FROM min_date) AND vf2.updated < (SELECT max_date FROM max_date))
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
defect_caused_by_commits_files AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
    array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf3.full_filename)), NULL) AS defect_caused_by_commits_files
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_defect td on ttrr.vc_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN testing_defect_caused_by_commits tdcabc ON td.id = tdcabc.defect_id
INNER JOIN vcs_filechange vfc3 on tdcabc.commit_id = vfc3.commit_id
INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
WHERE (
tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
OR vfc3.updated > (SELECT min_date FROM min_date) AND vfc3.updated < (SELECT max_date FROM max_date)
OR vf3.updated > (SELECT min_date FROM min_date) AND vf3.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
defect_caused_by_commits_messages AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
    array_cleanup((array_agg(DISTINCT vc.message)), NULL) AS defect_caused_by_commits_messages
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_defect td on ttrr.vc_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN testing_defect_caused_by_commits tdcabc ON td.id = tdcabc.defect_id
INNER JOIN vcs_commit vccbc on tdcabc.commit_id = vccbc.id
WHERE (
tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
defect_caused_by_commits_folders AS (
SELECT t.project_id,
	t.test_name,
	t.sha,
	t.rework,
	t.riskiness,
  array_cleanup(normalize_filepath_string(array_agg(DISTINCT t.folder)), NULL) AS defect_caused_by_commits_folders
FROM
(
	SELECT tt.project_id,
  tt.name as test_name,
	vc.sha,
	vc.rework,
	vc.riskiness,
	unnest(string_to_array(rtrim(vf3.full_filename, vf3.filename), '/')) AS folder
	FROM ttrr
	INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
	INNER JOIN testing_test tt on ttrr.tt_id = tt.id
	INNER JOIN testing_defect td on ttrr.vc_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
	INNER JOIN testing_defect_caused_by_commits tdcabc ON td.id = tdcabc.defect_id
	INNER JOIN vcs_filechange vfc3 on tdcabc.commit_id = vfc3.commit_id
	INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
	WHERE (
	tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
	OR vfc3.updated > (SELECT min_date FROM min_date) AND vfc3.updated < (SELECT max_date FROM max_date)
	OR vf3.updated > (SELECT min_date FROM min_date) AND vf3.updated < (SELECT max_date FROM max_date)
	)
) t
GROUP BY t.project_id,
t.test_name,
t.sha,
t.rework,
t.riskiness),
defect_caused_by_commits_areas AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
    array_cleanup(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_caused_by_commits_areas
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_defect td on ttrr.vc_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN testing_defect_caused_by_commits tdcabc ON td.id = tdcabc.defect_id
INNER JOIN vcs_commit_areas vca5 on tdcabc.commit_id = vca5.commit_id
INNER JOIN vcs_area va5 on vca5.area_id = va5.id
WHERE (tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
OR vca5.updated > (SELECT min_date FROM min_date) AND vca5.updated < (SELECT max_date FROM max_date)
OR va5.updated > (SELECT min_date FROM min_date) AND va5.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
defect_caused_by_commits_dependent_areas AS (
SELECT tt.project_id,
tt.name as test_name,
vc.sha,
vc.rework,
vc.riskiness,
    array_cleanup(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_caused_by_commits_dependent_areas
FROM ttrr
INNER JOIN vcs_commit vc on ttrr.vc_id = vc.id
INNER JOIN testing_test tt on ttrr.tt_id = tt.id
INNER JOIN testing_defect td on ttrr.vc_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
INNER JOIN testing_defect_caused_by_commits tdcabc ON td.id = tdcabc.defect_id
INNER JOIN vcs_commit_areas vca6 on tdcabc.commit_id = vca6.commit_id
INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
WHERE (
tdcabc.updated > (SELECT min_date FROM min_date) AND tdcabc.updated < (SELECT max_date FROM max_date)
OR vca6.updated > (SELECT min_date FROM min_date) AND vca6.updated < (SELECT max_date FROM max_date)
OR vad6.updated > (SELECT min_date FROM min_date) AND vad6.updated < (SELECT max_date FROM max_date)
OR va6.updated > (SELECT min_date FROM min_date) AND va6.updated < (SELECT max_date FROM max_date)
)
GROUP BY tt.project_id,
tt.name,
vc.sha,
vc.rework,
vc.riskiness),
files_since_last_run AS (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
array_cleanup(array_agg(ttrr.full_filename), NULL) AS files_since_last_run
FROM (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
normalize_filepath_string(full_trim(vcs_file.full_filename)) as full_filename
FROM vcs_file
	 INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
	 INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
INNER JOIN ttrr ON ttr.id = ttrr.test_run_id
EXCEPT
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
normalize_filepath_string(full_trim(vcs_file.full_filename)) as full_filename
FROM vcs_file
	 INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
	 INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
INNER JOIN ttrr ON  ttr.id = ttrr.previous_test_run_id) ttrr
GROUP BY ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id
),
folders_since_last_run AS (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
array_cleanup(array_agg(ttrr.foldername), NULL) AS folders_since_last_run
FROM (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/')))) as foldername
FROM vcs_file
	 INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
	 INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
INNER JOIN ttrr ON ttr.id = ttrr.test_run_id
EXCEPT
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/')))) as foldername
FROM vcs_file
	 INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
	 INNER JOIN testing_testrun ttr ON (ttr.commit_id = vf.commit_id)
INNER JOIN ttrr ON  ttr.id = ttrr.previous_test_run_id) ttrr
GROUP BY ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id
),
areas_since_last_run AS (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
array_cleanup(array_agg(ttrr.area_name), NULL) AS areas_since_last_run
FROM (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
lower(vcs_area.name) AS area_name
FROM vcs_area
INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
INNER JOIN ttrr ON ttr.id = ttrr.test_run_id
EXCEPT
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
lower(vcs_area.name) AS area_name
FROM vcs_area
INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
INNER JOIN ttrr ON  ttr.id = ttrr.previous_test_run_id) ttrr
GROUP BY ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id
),
dependent_areas_since_last_run AS (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
array_cleanup(array_agg(ttrr.area_name), NULL) AS dependent_areas_since_last_run
FROM (
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
lower(vcs_area.name) AS area_name
FROM vcs_area
INNER JOIN vcs_area_dependencies vad on vcs_area.id = vad.to_area_id
INNER JOIN vcs_commit_areas vca ON (vad.from_area_id = vca.area_id)
INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
INNER JOIN ttrr ON ttr.id = ttrr.test_run_id
EXCEPT
SELECT ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id,
lower(vcs_area.name) AS area_name
FROM vcs_area
INNER JOIN vcs_area_dependencies vad on vcs_area.id = vad.to_area_id
INNER JOIN vcs_commit_areas vca ON (vad.from_area_id = vca.area_id)
INNER JOIN testing_testrun ttr ON (ttr.commit_id = vca.commit_id)
INNER JOIN ttrr ON  ttr.id = ttrr.previous_test_run_id) ttrr
GROUP BY ttrr.test_run_id,
ttrr.previous_test_run_id,
ttrr.project_id,
ttrr.test_name,
ttrr.sha,
ttrr.rework,
ttrr.riskiness,
ttrr.tt_id
)

SELECT
    COALESCE(ttrr.test_changed, 0) AS test_changed,
ttrr.test_run_id,
ttrr.sha,
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
dccm.defect_caused_by_commits_messages AS defect_caused_by_commits_messages,
COALESCE(dccf.defect_caused_by_commits_files, file_slr.files_since_last_run) AS defect_caused_by_commits_files,
COALESCE(dcca.defect_caused_by_commits_areas, aslr.areas_since_last_run) AS defect_caused_by_commits_areas,
COALESCE(dccda.defect_caused_by_commits_dependent_areas, daslr.dependent_areas_since_last_run) AS defect_caused_by_commits_dependent_areas,
ttrr.defect_closed_by_caused_by_intersection_areas,
ttrr.defect_closed_by_caused_by_intersection_files,
ttrr.defect_closed_by_caused_by_intersection_folders,
ttrr.defect_closed_by_caused_by_intersection_dependent_areas,
COALESCE(dccfld.defect_caused_by_commits_folders, fold_slr.folders_since_last_run) AS defect_caused_by_commits_folders
FROM ttrr_grp ttrr
LEFT OUTER JOIN test_area_similarnamed tasn ON ttrr.project_id = tasn.project_id
LEFT OUTER JOIN test_associated_areas taa ON ttrr.project_id = taa.project_id
	and ttrr.test_name = taa.test_name
	and ttrr.sha = taa.sha
	and ttrr.rework = taa.rework
	and ttrr.riskiness = taa.riskiness
LEFT OUTER JOIN test_associated_files taf ON ttrr.project_id = taf.project_id
	and ttrr.test_name = taf.test_name
	and ttrr.sha = taf.sha
	and ttrr.rework = taf.rework
	and ttrr.riskiness = taf.riskiness
LEFT OUTER JOIN test_dependent_areas tda ON ttrr.project_id = tda.project_id
	and ttrr.test_name = tda.test_name
	and ttrr.sha = tda.sha
	and ttrr.rework = tda.rework
	and ttrr.riskiness = tda.riskiness
LEFT OUTER JOIN commit_areas ca ON ttrr.project_id = ca.project_id
	and ttrr.test_name = ca.test_name
	and ttrr.sha = ca.sha
	and ttrr.rework = ca.rework
	and ttrr.riskiness = ca.riskiness
LEFT OUTER JOIN commit_files cf ON ttrr.project_id = cf.project_id
	and ttrr.test_name = cf.test_name
	and ttrr.sha = cf.sha
	and ttrr.rework = cf.rework
	and ttrr.riskiness = cf.riskiness
LEFT OUTER JOIN defect_caused_by_commits_messages dccm ON ttrr.project_id = dccm.project_id
	and ttrr.test_name = dccm.test_name
	and ttrr.sha = dccm.sha
	and ttrr.rework = dccm.rework
	and ttrr.riskiness = dccm.riskiness
LEFT OUTER JOIN defect_caused_by_commits_files dccf ON ttrr.project_id = dccf.project_id
	and ttrr.test_name = dccf.test_name
	and ttrr.sha = dccf.sha
	and ttrr.rework = dccf.rework
	and ttrr.riskiness = dccf.riskiness
LEFT OUTER JOIN defect_caused_by_commits_areas dcca ON ttrr.project_id = dcca.project_id
	and ttrr.test_name = dcca.test_name
	and ttrr.sha = dcca.sha
	and ttrr.rework = dcca.rework
	and ttrr.riskiness = dcca.riskiness
LEFT OUTER JOIN defect_caused_by_commits_dependent_areas dccda ON ttrr.project_id = dccda.project_id
	and ttrr.test_name = dccda.test_name
	and ttrr.sha = dccda.sha
	and ttrr.rework = dccda.rework
	and ttrr.riskiness = dccda.riskiness
LEFT OUTER JOIN defect_caused_by_commits_folders dccfld ON ttrr.project_id = dccfld.project_id
	and ttrr.test_name = dccfld.test_name
	and ttrr.sha = dccfld.sha
	and ttrr.rework = dccfld.rework
	and ttrr.riskiness = dccfld.riskiness
LEFT OUTER JOIN files_since_last_run file_slr ON ttrr.project_id = file_slr.project_id
	and ttrr.tt_id = file_slr.tt_id
	and ttrr.test_name = file_slr.test_name
	and ttrr.sha = file_slr.sha
	and ttrr.rework = file_slr.rework
	and ttrr.riskiness = file_slr.riskiness
LEFT OUTER JOIN folders_since_last_run fold_slr ON ttrr.project_id = fold_slr.project_id
	and ttrr.tt_id = fold_slr.tt_id
	and ttrr.test_name = fold_slr.test_name
	and ttrr.sha = fold_slr.sha
	and ttrr.rework = fold_slr.rework
	and ttrr.riskiness = fold_slr.riskiness
LEFT OUTER JOIN areas_since_last_run aslr ON ttrr.project_id = aslr.project_id
	and ttrr.tt_id = aslr.tt_id
	and ttrr.test_name = aslr.test_name
	and ttrr.sha = aslr.sha
	and ttrr.rework = aslr.rework
	and ttrr.riskiness = aslr.riskiness
LEFT OUTER JOIN dependent_areas_since_last_run daslr ON ttrr.project_id = daslr.project_id
	and ttrr.tt_id = daslr.tt_id
	and ttrr.test_name = daslr.test_name
	and ttrr.sha = daslr.sha
	and ttrr.rework = daslr.rework
	and ttrr.riskiness = daslr.riskiness