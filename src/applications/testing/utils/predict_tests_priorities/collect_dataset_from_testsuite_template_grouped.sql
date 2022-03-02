WITH ttrr AS (
    SELECT
        CASE WHEN (tdcabc.defect_id IS NOT NULL OR tdclbc.defect_id IS NOT NULL) AND td.type IN (3,4) AND td.close_type IN (1,3) THEN 1 ELSE 0 END AS test_changed,
        tt.project_id,
        vc.sha,
        vc.rework,
        vc.riskiness,
        tdclbc.commit_id AS tdclbc_commit_id,
        tdcabc.commit_id AS tdcabc_commit_id,
        va.id AS va_id,
        tt.id AS tt_id,
        vc.id AS vc_id,
        tt.name as tt_name,
        tt.class_name,
        va.name as va_name
    FROM testing_testrunresult ttrr
        INNER JOIN vcs_commit vc on ttrr.commit_id = vc.id
        INNER JOIN testing_test tt on ttrr.test_id = tt.id
        INNER JOIN vcs_area va ON tt.area_id = va.id
        LEFT OUTER JOIN testing_defect td on ttrr.commit_id = td.created_by_commit_id and ttrr.test_run_id = td.created_by_test_run_id
        LEFT OUTER JOIN testing_defect_caused_by_commits tdcabc on td.id = tdcabc.defect_id
        LEFT OUTER JOIN testing_defect_closed_by_commits tdclbc on td.id = tdclbc.defect_id
    WHERE
        ttrr.test_suite_id = {test_suite_id}
),
ttrr_grp AS (
    SELECT
        ttrr.test_changed,
        ttrr.project_id,
        ttrr.sha,
        ttrr.rework,
        ttrr.riskiness,
        ttrr.tdclbc_commit_id,
        ttrr.tdcabc_commit_id,
    array_remove(array_agg(DISTINCT full_trim(ttrr.tt_name)), NULL) AS test_names,
    array_remove(array_agg(DISTINCT ttrr.class_name), NULL) AS test_classes_names,
    array_remove(array_agg(DISTINCT lower(ttrr.va_name)), NULL) AS test_areas,

    -- test_similarnamed(tt.project_id, string_agg(tt.name, ' '), string_agg(tt.class_name, ' ')) AS test_similarnamed,
    ARRAY [''] AS test_similarnamed,

    array_remove(array(
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
           WHERE ttrr.tdclbc_commit_id = vca.commit_id
           INTERSECT
           SELECT lower(vcs_area.name)
           FROM vcs_area
               INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id)
           WHERE ttrr.tdcabc_commit_id = vca.commit_id), NULL) AS defect_closed_by_caused_by_intersection_areas,
    array_remove(array(
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE ttrr.tdclbc_commit_id = vf.commit_id
           INTERSECT
           SELECT normalize_filepath_string(full_trim(vcs_file.full_filename))
           FROM vcs_file
               INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id)
           WHERE ttrr.tdcabc_commit_id = vf.commit_id
           ), NULL) AS defect_closed_by_caused_by_intersection_files
FROM ttrr
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
test_area_similarnamed AS (
SELECT ttrr.project_id,
         ttrr.test_areas,
         array_remove(test_area_similarnamed(ttrr.project_id, array_to_string(ttrr.test_areas, ' ')), NULL) AS test_area_similarnamed
FROM (SELECT project_id, test_areas FROM ttrr_grp GROUP BY project_id, test_areas ORDER BY 1, 2) ttrr
) ,
test_associated_areas AS (
SELECT ttrr.test_changed,
         ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,

array_remove(array_agg(DISTINCT lower(va2.name)), NULL) AS test_associated_areas

FROM ttrr
LEFT OUTER JOIN testing_test_associated_areas ttaa2 on ttrr.va_id = ttaa2.area_id
LEFT OUTER JOIN vcs_area va2 on ttaa2.area_id = va2.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
test_associated_files AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
array_remove(normalize_filepath_string(array_agg(DISTINCT vf.full_filename)), NULL) AS test_associated_files
FROM ttrr
LEFT OUTER JOIN testing_test_associated_files ttaf on ttrr.tt_id = ttaf.test_id
LEFT OUTER JOIN vcs_file vf on ttaf.file_id = vf.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
test_dependent_areas AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
    array_remove(array_agg(DISTINCT lower(va3.name)), NULL) AS test_dependent_areas
FROM ttrr
LEFT OUTER JOIN vcs_area_dependencies vad on ttrr.va_id = vad.to_area_id
LEFT OUTER JOIN testing_test_associated_areas ttaa3 on vad.from_area_id = ttaa3.area_id
LEFT OUTER JOIN vcs_area va3 on ttaa3.area_id = va3.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
commit_areas AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
         array_remove(normalize_filepath_string(array_agg(DISTINCT va4.name)), NULL) AS commit_areas
FROM ttrr
    LEFT OUTER JOIN vcs_commit_areas vca4 on ttrr.vc_id = vca4.commit_id
    LEFT OUTER JOIN vcs_area va4 on vca4.area_id = va4.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
commit_files AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf2.full_filename)), NULL) AS commit_files
FROM ttrr
    LEFT OUTER JOIN vcs_filechange vfc2 on ttrr.vc_id = vfc2.commit_id
    LEFT OUTER JOIN vcs_file vf2 on vfc2.file_id = vf2.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
defect_closed_by_caused_by_commits_files AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
    array_remove(normalize_filepath_string(array_agg(DISTINCT vf3.full_filename)), NULL) AS defect_closed_by_caused_by_commits_files
FROM ttrr_grp ttrr
    LEFT OUTER JOIN vcs_filechange vfc3 on ttrr.tdcabc_commit_id = vfc3.commit_id or ttrr.tdclbc_commit_id = vfc3.commit_id
    LEFT OUTER JOIN vcs_file vf3 on vf3.id = vfc3.file_id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
defect_closed_by_caused_by_commits_areas AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
    array_remove(array_agg(DISTINCT lower(va5.name)), NULL) AS defect_closed_by_caused_by_commits_areas
FROM ttrr_grp ttrr
    LEFT OUTER JOIN vcs_commit_areas vca5 on ttrr.tdcabc_commit_id = vca5.commit_id or ttrr.tdclbc_commit_id = vca5.commit_id
    LEFT OUTER JOIN vcs_area va5 on vca5.area_id = va5.id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id),
defect_closed_by_caused_by_commits_dependent_areas AS (
SELECT ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id,
    array_remove(array_agg(DISTINCT lower(va6.name)), NULL) AS defect_closed_by_caused_by_commits_dependent_areas
FROM ttrr_grp ttrr
    LEFT OUTER JOIN vcs_commit_areas vca6 on ttrr.tdcabc_commit_id = vca6.commit_id OR ttrr.tdclbc_commit_id = vca6.commit_id
    LEFT OUTER JOIN vcs_area_dependencies vad6 on vca6.area_id = vad6.from_area_id
    LEFT OUTER JOIN vcs_area va6 on va6.id = vad6.to_area_id
GROUP BY ttrr.test_changed,
ttrr.project_id,
         ttrr.sha,
         ttrr.rework,
         ttrr.riskiness,
         ttrr.tdclbc_commit_id,
         ttrr.tdcabc_commit_id)

SELECT ttrr.test_changed,
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
LEFT JOIN test_area_similarnamed tasn ON ttrr.project_id is not distinct from tasn.project_id
LEFT JOIN test_associated_areas taa ON ttrr.test_changed is not distinct from taa.test_changed
	and ttrr.project_id is not distinct from taa.project_id
	and ttrr.sha is not distinct from taa.sha
	and ttrr.rework is not distinct from taa.rework
	and ttrr.riskiness is not distinct from taa.riskiness
	and ttrr.tdclbc_commit_id is not distinct from taa.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from taa.tdcabc_commit_id
LEFT JOIN test_associated_files taf ON ttrr.test_changed is not distinct from taf.test_changed
	and ttrr.project_id is not distinct from taf.project_id
	and ttrr.sha is not distinct from taf.sha
	and ttrr.rework is not distinct from taf.rework
	and ttrr.riskiness is not distinct from taf.riskiness
	and ttrr.tdclbc_commit_id is not distinct from taf.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from taf.tdcabc_commit_id
LEFT JOIN test_dependent_areas tda ON ttrr.test_changed is not distinct from tda.test_changed
	and ttrr.project_id is not distinct from tda.project_id
	and ttrr.sha is not distinct from tda.sha
	and ttrr.rework is not distinct from tda.rework
	and ttrr.riskiness is not distinct from tda.riskiness
	and ttrr.tdclbc_commit_id is not distinct from tda.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from tda.tdcabc_commit_id
LEFT JOIN commit_areas ca ON ttrr.test_changed is not distinct from ca.test_changed
	and ttrr.project_id is not distinct from ca.project_id
	and ttrr.sha is not distinct from ca.sha
	and ttrr.rework is not distinct from ca.rework
	and ttrr.riskiness is not distinct from ca.riskiness
	and ttrr.tdclbc_commit_id is not distinct from ca.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from ca.tdcabc_commit_id
LEFT JOIN commit_files cf ON ttrr.test_changed is not distinct from cf.test_changed
	and ttrr.project_id is not distinct from cf.project_id
	and ttrr.sha is not distinct from cf.sha
	and ttrr.rework is not distinct from cf.rework
	and ttrr.riskiness is not distinct from cf.riskiness
	and ttrr.tdclbc_commit_id is not distinct from cf.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from cf.tdcabc_commit_id
LEFT JOIN defect_closed_by_caused_by_commits_files dccf ON ttrr.test_changed is not distinct from dccf.test_changed
	and ttrr.project_id is not distinct from dccf.project_id
	and ttrr.sha is not distinct from dccf.sha
	and ttrr.rework is not distinct from dccf.rework
	and ttrr.riskiness is not distinct from dccf.riskiness
	and ttrr.tdclbc_commit_id is not distinct from dccf.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from dccf.tdcabc_commit_id
LEFT JOIN defect_closed_by_caused_by_commits_areas dcca ON ttrr.test_changed is not distinct from dcca.test_changed
	and ttrr.project_id is not distinct from dcca.project_id
	and ttrr.sha is not distinct from dcca.sha
	and ttrr.rework is not distinct from dcca.rework
	and ttrr.riskiness is not distinct from dcca.riskiness
	and ttrr.tdclbc_commit_id is not distinct from dcca.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from dcca.tdcabc_commit_id
LEFT JOIN defect_closed_by_caused_by_commits_dependent_areas dccda ON ttrr.test_changed is not distinct from dccda.test_changed
	and ttrr.project_id is not distinct from dccda.project_id
	and ttrr.sha is not distinct from dccda.sha
	and ttrr.rework is not distinct from dccda.rework
	and ttrr.riskiness is not distinct from dccda.riskiness
	and ttrr.tdclbc_commit_id is not distinct from dccda.tdclbc_commit_id
	and ttrr.tdcabc_commit_id is not distinct from dccda.tdcabc_commit_id
;