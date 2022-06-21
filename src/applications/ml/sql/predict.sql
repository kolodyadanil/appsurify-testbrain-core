WITH
vc_id AS (SELECT unnest(array[{commits_ids}]) AS vc_id),
test_ids AS (SELECT unnest(array[{tests_ids}]) as test_id),
vc AS
(
    SELECT
        tt.id AS test_id,
        tt.project_id,
        vc.sha,
        vc.rework,
        vc.riskiness,
        va.id AS va_id,
        vc.id AS vc_id,
        tt.id AS tt_id,
        tt.name as tt_name,
        tt.class_name,
        va.name as va_name
    FROM vcs_commit vc
				INNER JOIN testing_test tt on tt.id IN (SELECT test_id FROM test_ids)
        INNER JOIN vcs_area va ON tt.area_id = va.id
    WHERE vc.id IN (SELECT vc_id FROM vc_id)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
),
vc_grp AS (
    SELECT
        vc.test_id,
        vc.project_id,
        vc.sha,
        vc.rework,
        vc.riskiness,
    array_cleanup(array_agg(DISTINCT full_trim(vc.tt_name)), NULL) AS test_names,
    array_cleanup(array_agg(DISTINCT vc.class_name), NULL) AS test_classes_names,
    array_cleanup(array_agg(DISTINCT lower(vc.va_name)), NULL) AS test_areas,
    string_agg(DISTINCT vc.va_name, ' ') AS va_names,

    NULL AS test_similarnamed,

    array_cleanup(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
           WHERE vca.commit_id IN (SELECT vc_id FROM vc_id)
					 ), NULL) AS defect_closed_by_caused_by_intersection_areas,
    array_cleanup(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE vf.commit_id IN (SELECT vc_id FROM vc_id)
           ), NULL) AS defect_closed_by_caused_by_intersection_files,
    array_cleanup(array(
           SELECT DISTINCT normalize_filepath_string(full_trim(unnest(string_to_array(rtrim(vcs_file.full_filename, vcs_file.filename), '/'))))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE vf.commit_id IN (SELECT vc_id FROM vc_id)
           ), NULL) AS defect_closed_by_caused_by_intersection_folders,
    array_cleanup(array(
           SELECT DISTINCT normalize_filepath_string(full_trim(va6.name))
           FROM vcs_commit_areas vca6
               INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
               INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
           WHERE vca6.commit_id IN (SELECT vc_id FROM vc_id)
           ), NULL) AS defect_closed_by_caused_by_intersection_dependent_areas
FROM vc
GROUP BY vc.test_id,
         vc.project_id,
         vc.sha,
         vc.rework,
         vc.riskiness),
test_area_similarnamed AS (
SELECT vc.project_id,
         vc.test_areas,
         array_cleanup(test_area_similarnamed(vc.project_id, array_to_string(vc.test_areas, ' ')), NULL) AS test_area_similarnamed
FROM (SELECT project_id, test_areas FROM vc_grp GROUP BY project_id, test_areas ORDER BY 1, 2) vc
),
test_associated_areas AS (
SELECT vc.test_id,
array_cleanup(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas
FROM vc
INNER JOIN testing_test_associated_areas ttaa2 on vc.va_id = ttaa2.area_id
INNER JOIN vcs_area va2 on ttaa2.area_id = va2.id
GROUP BY vc.test_id),
test_associated_files AS (
SELECT vc.test_id,
array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf.full_filename)), NULL) AS test_associated_files
FROM vc
INNER JOIN testing_test_associated_files ttaf on vc.test_id = ttaf.test_id
INNER JOIN vcs_file vf on ttaf.file_id = vf.id
GROUP BY vc.test_id),
test_dependent_areas AS (
SELECT vc.test_id,
array_cleanup(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas
FROM vc
INNER JOIN vcs_area_dependencies vad on vc.va_id = vad.to_area_id
INNER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
INNER JOIN vcs_area va3 on ttaa3.area_id = va3.id
GROUP BY vc.test_id),
commit_areas AS (
SELECT vc.test_id,
array_cleanup(normalize_filepath_string(array_agg(DISTINCT va4.name)), NULL) AS commit_areas
FROM vc
INNER JOIN vcs_commit_areas vca4 on vc.vc_id = vca4.commit_id
INNER JOIN vcs_area va4 on vca4.area_id = va4.id
GROUP BY vc.test_id),
commit_files AS (
SELECT vc.test_id,
    array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf2.full_filename)), NULL) AS commit_files
FROM vc
INNER JOIN vcs_filechange vfc2 on vc.vc_id = vfc2.commit_id
INNER JOIN vcs_file vf2 on vfc2.file_id = vf2.id
GROUP BY vc.test_id),
defect_caused_by_commits_files AS (
SELECT vc.test_id,
    array_cleanup(normalize_filepath_string(array_agg(DISTINCT vf3.full_filename)), NULL) AS defect_caused_by_commits_files
FROM vc
INNER JOIN vcs_filechange vfc3 on vfc3.commit_id = vc.vc_id
INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
GROUP BY vc.test_id),
defect_caused_by_commits_folders AS (
SELECT t.test_id,
    array_cleanup(normalize_filepath_string(array_agg(DISTINCT t.folder)), NULL) AS defect_caused_by_commits_folders
FROM
(
	SELECT vc.test_id, unnest(string_to_array(rtrim(vf3.full_filename, vf3.filename), '/')) AS folder
	FROM vc
	INNER JOIN vcs_filechange vfc3 on vfc3.commit_id = vc.vc_id
	INNER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
) t
GROUP BY t.test_id),
defect_caused_by_commits_areas AS (
SELECT vc.test_id,
    array_cleanup(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_caused_by_commits_areas
FROM vc
INNER JOIN vcs_commit_areas vca5 on vca5.commit_id = vc.vc_id
INNER JOIN vcs_area va5 on vca5.area_id = va5.id
GROUP BY vc.test_id),
defect_caused_by_commits_dependent_areas AS (
SELECT vc.test_id,
    array_cleanup(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_caused_by_commits_dependent_areas
FROM vc
INNER JOIN vcs_commit_areas vca6 on vca6.commit_id = vc.vc_id
INNER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
INNER JOIN vcs_area va6 on va6.id = vad6.to_area_id
GROUP BY vc.test_id)

SELECT vc.test_id,
vc.project_id,
vc.test_names,
vc.test_classes_names,
vc.test_areas,
vc.va_names,
taa.test_associated_areas,
taf.test_associated_files,
tda.test_dependent_areas,
vc.test_similarnamed,
tasn.test_area_similarnamed,
vc.rework AS commit_rework,
vc.riskiness::numeric::integer * 100 AS commit_riskiness,
ca.commit_areas,
cf.commit_files,
dccf.defect_caused_by_commits_files,
dcca.defect_caused_by_commits_areas,
dccda.defect_caused_by_commits_dependent_areas,
vc.defect_closed_by_caused_by_intersection_areas,
vc.defect_closed_by_caused_by_intersection_files,
vc.defect_closed_by_caused_by_intersection_folders,
vc.defect_closed_by_caused_by_intersection_dependent_areas,
dccfld.defect_caused_by_commits_folders
FROM vc_grp vc
LEFT OUTER JOIN test_area_similarnamed tasn ON vc.project_id = tasn.project_id AND vc.test_areas = tasn.test_areas
LEFT OUTER JOIN test_associated_areas taa ON vc.test_id = taa.test_id
LEFT OUTER JOIN test_associated_files taf ON vc.test_id = taf.test_id
LEFT OUTER JOIN test_dependent_areas tda ON vc.test_id = tda.test_id
LEFT OUTER JOIN commit_areas ca ON vc.test_id = ca.test_id
LEFT OUTER JOIN commit_files cf ON vc.test_id = cf.test_id
LEFT OUTER JOIN defect_caused_by_commits_files dccf ON vc.test_id = dccf.test_id
LEFT OUTER JOIN defect_caused_by_commits_areas dcca ON vc.test_id = dcca.test_id
LEFT OUTER JOIN defect_caused_by_commits_dependent_areas dccda ON vc.test_id = dccda.test_id
LEFT OUTER JOIN defect_caused_by_commits_folders dccfld ON vc.test_id = dccfld.test_id