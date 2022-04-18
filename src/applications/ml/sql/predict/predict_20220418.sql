WITH
vc_id AS (SELECT unnest(array[{commits_ids}]) AS vc_id),
test_ids AS (SELECT unnest(array[{tests_ids}]) as test_id),
ttrr AS
(
    SELECT
        ttrr.test_id,
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
        ttrr.test_id IN (SELECT test_id FROM test_ids) AND vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
),
ttrr_grp AS (
    SELECT
        ttrr.test_id,
        ttrr.project_id,
        ttrr.sha,
        ttrr.rework,
        ttrr.riskiness,
    array_remove(array_agg(DISTINCT full_trim(ttrr.tt_name)), NULL) AS test_names,
    array_remove(array_agg(DISTINCT ttrr.class_name), NULL) AS test_classes_names,
    array_remove(array_agg(DISTINCT lower(ttrr.va_name)), NULL) AS test_areas,
    string_agg(DISTINCT ttrr.va_name, ' ') AS va_names,

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
GROUP BY ttrr.test_id,
         ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
				 ttrr.td_id),
test_area_similarnamed AS (
SELECT ttrr.project_id,
         ttrr.test_areas,
         array_remove(test_area_similarnamed(ttrr.project_id, array_to_string(ttrr.test_areas, ' ')), NULL) AS test_area_similarnamed
FROM (SELECT project_id, test_areas FROM ttrr_grp GROUP BY project_id, test_areas ORDER BY 1, 2) ttrr
),
test_associated_areas AS (
SELECT ttrr.test_id,
array_remove(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas
FROM ttrr
INNER JOIN testing_test_associated_areas ttaa2 on ttrr.va_id = ttaa2.area_id
INNER JOIN vcs_area va2 on ttaa2.area_id = va2.id
GROUP BY ttrr.test_id),
test_associated_files AS (
SELECT ttrr.test_id,
array_remove(normalize_filepath_string(array_agg(DISTINCT vf.full_filename)), NULL) AS test_associated_files
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN testing_test_associated_files ttaf on ttrr.test_id = ttaf.test_id
INNER JOIN vcs_file vf on ttaf.file_id = vf.id
WHERE ttrr.test_id IN (SELECT test_id FROM test_ids) AND vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY ttrr.test_id),
test_dependent_areas AS (
SELECT ttrr.test_id,
array_remove(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_area_dependencies vad on ttrr.area_id = vad.to_area_id
INNER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
INNER JOIN vcs_area va3 on ttaa3.area_id = va3.id
WHERE ttrr.test_id IN (SELECT test_id FROM test_ids) AND vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY ttrr.test_id),
commit_areas AS (
SELECT ttrr.test_id,
array_remove(normalize_filepath_string(array_agg(DISTINCT va4.name)), NULL) AS commit_areas
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_commit_areas vca4 on ttrr.commit_id = vca4.commit_id
INNER JOIN vcs_area va4 on vca4.area_id = va4.id
WHERE ttrr.test_id IN (SELECT test_id FROM test_ids) AND vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY ttrr.test_id),
commit_files AS (
SELECT ttrr.test_id,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf2.full_filename)), NULL) AS commit_files
FROM testing_testrunresult ttrr
INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
INNER JOIN testing_test tt on ttrr.test_id = tt.id
INNER JOIN vcs_filechange vfc2 on ttrr.commit_id = vfc2.commit_id
INNER JOIN vcs_file vf2 on vfc2.file_id = vf2.id
WHERE ttrr.test_id IN (SELECT test_id FROM test_ids) AND vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY ttrr.test_id),
defect_closed_by_caused_by_commits_files AS (
SELECT ttrr.test_id,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf3.full_filename)), NULL) AS defect_closed_by_caused_by_commits_files
FROM ttrr
INNER JOIN testing_defect_caused_by_commits tdcabc ON tdcabc.defect_id = ttrr.td_id
INNER JOIN testing_defect_closed_by_commits tdclbc ON tdclbc.defect_id = ttrr.td_id AND (tdcabc.commit_id IS NULL OR tdcabc.commit_id = tdclbc.commit_id)
INNER JOIN vcs_filechange vfc3 on vfc3.commit_id IN (tdcabc.commit_id, tdclbc.commit_id)
INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
GROUP BY ttrr.test_id),
defect_closed_by_caused_by_commits_areas AS (
SELECT ttrr.test_id,
    array_remove(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_closed_by_caused_by_commits_areas
FROM ttrr
INNER JOIN testing_defect_caused_by_commits tdcabc ON tdcabc.defect_id = ttrr.td_id
INNER JOIN testing_defect_closed_by_commits tdclbc ON tdclbc.defect_id = ttrr.td_id AND (tdcabc.commit_id IS NULL OR tdcabc.commit_id = tdclbc.commit_id)
INNER JOIN vcs_commit_areas vca5 on vca5.commit_id IN (tdcabc.commit_id, tdclbc.commit_id)
INNER JOIN vcs_area va5 on vca5.area_id = va5.id
GROUP BY ttrr.test_id),
defect_closed_by_caused_by_commits_dependent_areas AS (
SELECT ttrr.test_id,
    array_remove(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_closed_by_caused_by_commits_dependent_areas
FROM ttrr
INNER JOIN testing_defect_caused_by_commits tdcabc ON tdcabc.defect_id = ttrr.td_id
INNER JOIN testing_defect_closed_by_commits tdclbc ON tdclbc.defect_id = ttrr.td_id AND (tdcabc.commit_id IS NULL OR tdcabc.commit_id = tdclbc.commit_id)
INNER JOIN vcs_commit_areas vca6 on vca6.commit_id IN (tdcabc.commit_id, tdclbc.commit_id)
INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
GROUP BY ttrr.test_id)

SELECT ttrr.test_id,
ttrr.project_id,
ttrr.test_names,
ttrr.test_classes_names,
ttrr.test_areas,
ttrr.va_names,
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
LEFT OUTER JOIN test_area_similarnamed tasn ON ttrr.project_id = tasn.project_id AND ttrr.test_areas = tasn.test_areas
LEFT OUTER JOIN test_associated_areas taa ON ttrr.test_id = taa.test_id
LEFT OUTER JOIN test_associated_files taf ON ttrr.test_id = taf.test_id
LEFT OUTER JOIN test_dependent_areas tda ON ttrr.test_id = tda.test_id
LEFT OUTER JOIN commit_areas ca ON ttrr.test_id = ca.test_id
LEFT OUTER JOIN commit_files cf ON ttrr.test_id = cf.test_id
LEFT OUTER JOIN defect_closed_by_caused_by_commits_files dccf ON ttrr.test_id = dccf.test_id
LEFT OUTER JOIN defect_closed_by_caused_by_commits_areas dcca ON ttrr.test_id = dcca.test_id
LEFT OUTER JOIN defect_closed_by_caused_by_commits_dependent_areas dccda ON ttrr.test_id = dccda.test_id