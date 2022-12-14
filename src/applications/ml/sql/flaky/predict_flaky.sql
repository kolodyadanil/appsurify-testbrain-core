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
    AND defect_id in {defect_ids}
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
  array_remove(array_agg(DISTINCT lower(ttrr2.areas)), NULL) AS areas,
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(full_trim(ttrr2.files))
    ),
    NULL
  ) AS files,
  array_remove(array_agg(DISTINCT lower(ttrr3.areas)), NULL) AS failedAreas,
  array_remove(
    array_agg(
      DISTINCT normalize_filepath_string(full_trim(ttrr3.files))
    ),
    NULL
  ) AS failedFiles,
  CASE WHEN  td.type IN (2) THEN 1 ELSE 0 END AS defectType,
  AVG(ttrr.execution_time) AS averageRuntimeWhenPass,
  AVG(ttrr4.execution_time) AS runTime,
  COUNT (DISTINCT (tdat.ID)) AS numberOfTests,
  COUNT (DISTINCT (tdftr.ID)) AS numberOfFoundTestRuns,
  COUNT (DISTINCT (tdfc.ID)) AS numberOfFoundCommits,
  COUNT (DISTINCT (tdrc.ID)) AS numberOfReopenCommits,
  COUNT (DISTINCT (tdrtr.ID)) AS numberOfReopenTestRuns,
  COUNT (DISTINCT (tdcbt.ID)) AS numberOfCreatedByTests,
  COUNT (DISTINCT (tdrt.ID)) AS numberOfReopenedByTests,
  CASE
    WHEN COUNT(DISTINCT(tdrt.id)) = 0 THEN NULL
    ELSE COUNT(DISTINCT(tdrtr.id)) / COUNT(DISTINCT(tdrt.id))
  END AS reopenedTestRunsByReopenedTests,
  CASE
    WHEN COUNT(DISTINCT(tdcbt.id)) = 0 THEN NULL
    ELSE COUNT(DISTINCT(tdcbtr.id)) / COUNT(DISTINCT(tdcbt.id))
  END AS createdTestRunsByCreatedTests
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
  td.type