WITH td AS (
  SELECT 
    id, 
    name, 
    error, 
    reason, 
    type, 
    created_by_commit_id, 
    created_by_test_run_id, 
    created_by_test_id 
  FROM 
    testing_defect 
  WHERE 
    project_id IN (426) 
    and created_by_commit_id is not null 
    and created_by_test_run_id is not null 
    and created_by_test_id is not null
), 
ttrr AS (
  SELECT 
    test_run_id, 
    commit_id, 
    AVG(execution_time) as execution_time 
  FROM 
    testing_testrunresult 
  WHERE 
    project_id IN (426) 
    AND status = 'pass' 
  GROUP BY 
    test_run_id, 
    commit_id
), 
tt AS (
  SELECT 
    id 
  FROM 
    testing_test 
  WHERE 
    project_id IN (426)
), 
va AS (
  SELECT 
    id, 
    name 
  FROM 
    vcs_area 
  WHERE 
    project_id IN (426)
), 
vf AS (
  SELECT 
    id, 
    full_filename 
  FROM 
    vcs_file 
  WHERE 
    project_id IN (426)
) 
SELECT 
  td.ID, 
  td.name, 
  td.error, 
  td.reason, 
  array_remove(
    array_agg(
      DISTINCT lower(va.name)
    ), 
    NULL
  ) AS areas, 
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(
        full_trim(vf.full_filename)
      )
    ), 
    NULL
  ) AS files, 
  CASE WHEN td.type = 1 THEN 'Environmental' WHEN td.type = 2 THEN 'Flaky' WHEN td.type = 3 THEN 'Project' WHEN td.type = 4 THEN 'Invalid Test' WHEN td.type = 5 THEN 'Local' WHEN td.type = 6 THEN 'Outside' WHEN td.type = 7 THEN 'New Test' END AS defectType, 
  AVG(ttrr.execution_time) AS averageRuntime, 
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
  LEFT JOIN tt on td.created_by_test_id = tt.id 
  LEFT JOIN testing_test_associated_areas ttaa on tt.id = ttaa.test_id 
  LEFT JOIN vcs_area va on ttaa.area_id = va.id 
  LEFT JOIN testing_test_associated_files ttaf on tt.id = ttaf.test_id 
  LEFT JOIN vcs_file vf on ttaf.file_id = vf.id 
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
  td.type
