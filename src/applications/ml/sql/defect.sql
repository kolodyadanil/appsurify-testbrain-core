WITH td AS (
  SELECT 
    id, 
    name, 
    error, 
    reason, 
    type, 
    created_by_commit_id, 
    created_by_test_run_id, 
    created_by_test_id, 
    created_by_test_run_result_id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN {project_ids} 
    AND created_by_commit_id IS NOT NULL 
    AND created_by_test_run_id IS NOT NULL 
    AND created_by_test_id IS NOT NULL 
    AND created_by_test_run_result_id IS NOT NULL
), 
ttrr AS (
  SELECT 
    test_run_id, 
    commit_id, 
    AVG(execution_time) AS execution_time 
  FROM 
    testing_testrunresult 
  WHERE 
    project_id IN {project_ids} 
    AND status = 'pass' 
  GROUP BY 
    test_run_id, 
    commit_id
), 
ttrr2 AS (
  SELECT 
    test_run_id, 
    commit_id, 
    va.name AS areas, 
    vf.full_filename AS files 
  FROM 
    testing_testrunresult 
    INNER JOIN (
      SELECT 
        id, 
        area_id 
      FROM 
        testing_test 
      WHERE 
        project_id IN {project_ids}
    ) tt ON testing_testrunresult.test_id = tt.id 
    INNER JOIN (
      SELECT 
        id, 
        name 
      FROM 
        vcs_area 
      WHERE 
        project_id IN {project_ids}
    ) va ON tt.area_id = va.id 
    LEFT JOIN vcs_file_areas vfa ON vfa.area_id = va.id 
    LEFT JOIN (
      SELECT 
        id, 
        full_filename 
      FROM 
        vcs_file 
      WHERE 
        project_id IN {project_ids}
    ) vf ON vfa.file_id = vf.id 
  WHERE 
    project_id IN {project_ids} 
  GROUP BY 
    test_run_id, 
    commit_id, 
    va.name, 
    vf.full_filename
), 
ttrr3 AS (
  SELECT 
    test_run_id, 
    commit_id, 
    va.name AS areas, 
    vf.full_filename AS files 
  FROM 
    testing_testrunresult 
    INNER JOIN (
      SELECT 
        id, 
        area_id 
      FROM 
        testing_test 
      WHERE 
        project_id IN {project_ids}
    ) tt ON testing_testrunresult.test_id = tt.id 
    INNER JOIN (
      SELECT 
        id, 
        name 
      FROM 
        vcs_area 
      WHERE 
        project_id IN {project_ids}
    ) va ON tt.area_id = va.id 
    LEFT JOIN vcs_file_areas vfa ON vfa.area_id = va.id 
    LEFT JOIN (
      SELECT 
        id, 
        full_filename 
      FROM 
        vcs_file 
      WHERE 
        project_id IN {project_ids}
    ) vf ON vfa.file_id = vf.id 
  WHERE 
    project_id IN {project_ids} 
    AND status = 'fail' 
  GROUP BY 
    test_run_id, 
    commit_id, 
    va.name, 
    vf.full_filename 
  ORDER BY 
    test_run_id
), 
ttrr4 AS (
  SELECT 
    id, 
    AVG(execution_time) AS execution_time 
  FROM 
    testing_testrunresult 
  WHERE 
    project_id IN {project_ids} 
    AND status = 'fail' 
  GROUP BY 
    id
) 
SELECT 
  td.ID, 
  td.name, 
  td.error, 
  td.reason, 
  array_remove(
    array_agg(
      DISTINCT lower(ttrr2.areas)
    ), 
    NULL
  ) AS areas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(ttrr2.files)
      )
    ), 
    NULL
  ) AS files, 
  array_remove(
    array_agg(
      DISTINCT lower(ttrr3.areas)
    ), 
    NULL
  ) AS failedAreas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(ttrr3.files)
      )
    ), 
    NULL
  ) AS failedFiles, 
  CASE WHEN td.type = 1 THEN 'Environmental' WHEN td.type = 2 THEN 'Flaky' WHEN td.type = 3 THEN 'Project' WHEN td.type = 4 THEN 'Invalid Test' WHEN td.type = 5 THEN 'Local' WHEN td.type = 6 THEN 'Outside' WHEN td.type = 7 THEN 'New Test' END AS defectType, 
  AVG(ttrr.execution_time) AS averageRuntimeWhenPass, 
  AVG(ttrr4.execution_time) AS runTime, 
  COUNT (
    DISTINCT (tdat.ID)
  ) AS numberOfTests, 
  COUNT (
    DISTINCT (tdftr.ID)
  ) AS numberOfFountTestRuns, 
  COUNT (
    DISTINCT (tdfc.ID)
  ) AS numberOfFoundCommits, 
  COUNT (
    DISTINCT (tdrc.ID)
  ) AS numberOfReopenCommits, 
  COUNT (
    DISTINCT (tdrtr.ID)
  ) AS numberOfReopenTestRuns, 
  COUNT (
    DISTINCT (tdcbt.ID)
  ) AS numberOfCreatedByTests, 
  COUNT (
    DISTINCT (tdrt.ID)
  ) AS numberOfReopenedByTests, 
  CASE WHEN COUNT(
    DISTINCT(tdrt.id)
  ) = 0 THEN NULL ELSE COUNT(
    DISTINCT(tdrtr.id)
  ) / COUNT(
    DISTINCT(tdrt.id)
  ) END AS reopenedTestRunsByReopenedTests, 
  CASE WHEN COUNT(
    DISTINCT(tdcbt.id)
  ) = 0 THEN NULL ELSE COUNT(
    DISTINCT(tdcbtr.id)
  ) / COUNT(
    DISTINCT(tdcbt.id)
  ) END AS createdTestRunsByCreatedTests 
FROM 
  td 
  LEFT JOIN ttrr ON ttrr.commit_id = td.created_by_commit_id 
  AND ttrr.test_run_id = td.created_by_test_run_id 
  LEFT JOIN ttrr2 ON ttrr2.commit_id = td.created_by_commit_id 
  AND ttrr2.test_run_id = td.created_by_test_run_id 
  LEFT JOIN ttrr3 ON ttrr3.commit_id = td.created_by_commit_id 
  AND ttrr3.test_run_id = td.created_by_test_run_id 
  LEFT JOIN ttrr4 ON ttrr4.id = td.created_by_test_run_result_id 
  LEFT JOIN testing_defect_associated_tests tdat ON tdat.defect_id = td.ID 
  LEFT JOIN testing_defect_found_test_runs tdftr ON tdftr.defect_id = td.ID 
  LEFT JOIN testing_defect_found_commits tdfc ON tdfc.defect_id = td.ID 
  LEFT JOIN testing_defect_reopen_commits tdrc ON tdrc.defect_id = td.ID 
  LEFT JOIN testing_defect_reopen_test_runs tdrtr ON tdrtr.defect_id = td.ID 
  LEFT JOIN testing_defect_caused_by_tests tdcbt ON tdcbt.defect_id = td.ID 
  LEFT JOIN testing_defect_reopen_tests tdrt ON tdrt.defect_id = td.ID 
  LEFT JOIN testing_defect_caused_by_test_runs tdcbtr ON tdcbtr.defect_id = td.ID 
GROUP BY 
  td.ID, 
  td.name, 
  td.error, 
  td.reason, 
  td.type;
WITH td2 AS (
  SELECT 
    id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN {project_ids} 
    AND created_by_commit_id IS NOT NULL 
    AND created_by_test_run_id IS NOT NULL 
    AND created_by_test_id IS NOT NULL 
    AND created_by_test_run_result_id IS NOT NULL
) 
SELECT 
  td2.id, 
  array_remove(
    array_agg(
      DISTINCT lower(va.name)
    ), 
    NULL
  ) AS defect_caused_by_commits_areas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(vf.full_filename)
      )
    ), 
    NULL
  ) AS defect_caused_by_commits_files 
FROM 
  td2 
  LEFT JOIN testing_defect_caused_by_commits tdcabc ON td2.id = tdcabc.defect_id 
  LEFT JOIN vcs_filechange vfc ON tdcabc.commit_id = vfc.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      full_filename 
    FROM 
      vcs_file 
    WHERE 
      project_id IN {project_ids}
  ) vf ON vf.id = vfc.file_id 
  LEFT JOIN vcs_commit_areas vca ON tdcabc.commit_id = vca.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      name 
    FROM 
      vcs_area 
    WHERE 
      project_id IN {project_ids}
  ) va ON vca.area_id = va.id 
GROUP BY 
  td2.id;
WITH td2 AS (
  SELECT 
    id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN {project_ids} 
    AND created_by_commit_id IS NOT NULL 
    AND created_by_test_run_id IS NOT NULL 
    AND created_by_test_id IS NOT NULL 
    AND created_by_test_run_result_id IS NOT NULL
) 
SELECT 
  td2.id, 
  array_remove(
    array_agg(
      DISTINCT lower(va.name)
    ), 
    NULL
  ) AS defect_reopen_commits_areas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(vf.full_filename)
      )
    ), 
    NULL
  ) AS defect_reopen_commits_files 
FROM 
  td2 
  LEFT JOIN testing_defect_reopen_commits tdrc ON td2.id = tdrc.defect_id 
  LEFT JOIN vcs_filechange vfc ON tdrc.commit_id = vfc.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      full_filename 
    FROM 
      vcs_file 
    WHERE 
      project_id IN {project_ids}
  ) vf ON vf.id = vfc.file_id 
  LEFT JOIN vcs_commit_areas vca ON tdrc.commit_id = vca.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      name 
    FROM 
      vcs_area 
    WHERE 
      project_id IN {project_ids}
  ) va ON vca.area_id = va.id 
GROUP BY 
  td2.id;
WITH td2 AS (
  SELECT 
    id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN {project_ids} 
    AND created_by_commit_id IS NOT NULL 
    AND created_by_test_run_id IS NOT NULL 
    AND created_by_test_id IS NOT NULL 
    AND created_by_test_run_result_id IS NOT NULL
) 
SELECT 
  td2.id, 
  array_remove(
    array_agg(
      DISTINCT lower(va.name)
    ), 
    NULL
  ) AS defect_found_commits_areas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(vf.full_filename)
      )
    ), 
    NULL
  ) AS defect_found_commits_files 
FROM 
  td2 
  LEFT JOIN testing_defect_found_commits tdfc ON td2.id = tdfc.defect_id 
  LEFT JOIN vcs_filechange vfc ON tdfc.commit_id = vfc.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      full_filename 
    FROM 
      vcs_file 
    WHERE 
      project_id IN {project_ids}
  ) vf ON vf.id = vfc.file_id 
  LEFT JOIN vcs_commit_areas vca ON tdfc.commit_id = vca.commit_id 
  LEFT JOIN (
    SELECT 
      id, 
      name 
    FROM 
      vcs_area 
    WHERE 
      project_id IN {project_ids}
  ) va ON vca.area_id = va.id 
GROUP BY 
  td2.id;
WITH td AS (
  SELECT 
    id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN {project_ids} 
    AND created_by_commit_id IS NOT NULL 
    AND created_by_test_run_id IS NOT NULL 
    AND created_by_test_id IS NOT NULL 
    AND created_by_test_run_result_id IS NOT NULL
) 
SELECT 
  td.ID, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(vf3.full_filename)
      )
    ), 
    NULL
  ) AS defect_closed_by_caused_by_commits_files, 
  array_remove(
    array_agg(
      DISTINCT lower(va5.name)
    ), 
    NULL
  ) AS defect_closed_by_caused_by_commits_areas, 
  array_remove(
    array(
      SELECT 
        lower(vcs_area.name) 
      FROM 
        vcs_area 
        INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) 
      WHERE 
        tdclbc.commit_id = vca.commit_id 
      INTERSECT 
      SELECT 
        lower(vcs_area.name) 
      FROM 
        vcs_area 
        INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) 
      WHERE 
        tdcabc.commit_id = vca.commit_id
    ), 
    NULL
  ) AS defect_closed_by_caused_by_intersection_areas, 
  array_remove(
    array(
      SELECT 
        normalize_filepath_string(
          full_trim(vcs_file.full_filename)
        ) 
      FROM 
        vcs_file 
        INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) 
      WHERE 
        tdclbc.commit_id = vf.commit_id 
      INTERSECT 
      SELECT 
        normalize_filepath_string(
          full_trim(vcs_file.full_filename)
        ) 
      FROM 
        vcs_file 
        INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) 
      WHERE 
        tdcabc.commit_id = vf.commit_id
    ), 
    NULL
  ) AS defect_closed_by_caused_by_intersection_files 
FROM 
  td 
  LEFT OUTER JOIN testing_defect_caused_by_commits tdcabc on td.id = tdcabc.defect_id 
  LEFT OUTER JOIN testing_defect_closed_by_commits tdclbc on td.id = tdclbc.defect_id 
  LEFT OUTER JOIN vcs_filechange vfc3 on tdcabc.commit_id = vfc3.commit_id 
  or tdclbc.commit_id = vfc3.commit_id 
  LEFT OUTER JOIN (
    select 
      id, 
      full_filename 
    from 
      vcs_file 
    where 
      project_id in {project_ids}
  ) vf3 on vf3.id = vfc3.file_id 
  LEFT OUTER JOIN vcs_commit_areas vca5 on tdcabc.commit_id = vca5.commit_id 
  or tdclbc.commit_id = vca5.commit_id 
  LEFT OUTER JOIN (
    select 
      id, 
      name 
    from 
      vcs_area 
    where 
      project_id in {project_ids}
  ) va5 on vca5.area_id = va5.id 
GROUP BY 
  td.ID, 
  tdclbc.commit_id, 
  tdcabc.commit_id;
