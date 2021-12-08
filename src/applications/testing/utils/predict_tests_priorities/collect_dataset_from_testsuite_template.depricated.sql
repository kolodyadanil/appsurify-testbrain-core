-- We collect only those data:
--  test_result_type                                   # + | ('Change', 'Same')
--  test_name                                          # + | test name
--  test_class_name                                    # + | test class name
--  test_area                                          # + | test area name
--  test_associated_areas                              # + | list of names of areas that associated with test in this row
--  test_associated_files                              # + | list of names of files that associated with test in this row
--  test_dependent_areas                               # + | list of names of areas that depend of areas associated with test in this row
--  test_similarnamed                                  # + | Data for this field will be added later in results of this script.
--  test_area_similarnamed                             # + | Data for this field will be added later in results of this script.
--
--  commit_rework                                      # + | just value from commit.rework
--  commit_riskiness                                   # + | just value from commit.riskiness
--  commit_areas                                       # + | list of names areas that associated with current commit
--  commit_files                                       # + | list of filenames that associated with current commit
--
--  defect_closed_by_caused_by_commits_files           # + | list of filenames that associated with commits that caused defect or closed by
--  defect_closed_by_caused_by_commits_areas           # + | list of filenames that associated with commits that caused defect or closed by
--  defect_closed_by_caused_by_commits_dependent_areas # + | list of filenames that associated with commits that caused defect or closed by
--
--  defect_closed_by_caused_by_intersection_files      # + | list of filenames that associated with commits on that current defect was closed AND on what caused its
--  defect_closed_by_caused_by_intersection_areas      # + | list of name of areas that associated with commits on that current defect was closed AND on what caused its
SELECT
       (
           CASE
               WHEN tdcabc.id NOTNULL AND commit_defect.type IN (3,4) AND commit_defect.close_type IN (1,3) THEN 'Change'
               WHEN tdclbc.id NOTNULL AND commit_defect.type IN (3,4) AND commit_defect.close_type IN (1,3) THEN 'Change'
               ELSE 'Same'
           END
       ) AS test_result_type,
       testing_test.name AS test_name, testing_test.class_name AS test_class_name, va.name AS test_area,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN testing_test_associated_areas ttaa ON (vcs_area.id = ttaa.area_id) WHERE ttaa.test_id = testing_test.id), ',') AS test_associated_areas,
       array_to_string(array(SELECT vcs_file.full_filename FROM vcs_file INNER JOIN testing_test_associated_files ttaf ON (vcs_file.id = ttaf.file_id) WHERE ttaf.test_id = testing_test.id), ',') AS test_associated_files,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_area_dependencies vad ON (vcs_area.id = vad.to_area_id) INNER JOIN testing_test_associated_areas ttaa ON (vad.from_area_id = ttaa.area_id) WHERE ttaa.test_id = testing_test.id), ',') AS test_dependent_areas,
       '' AS test_similarnamed,
       '' AS test_area_similarnamed,
       vc.rework AS commit_rework,
       vc.riskiness AS commit_riskiness,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) WHERE vca.commit_id = vc.id), ',') AS commit_areas,
       array_to_string(array(SELECT vcs_file.full_filename FROM vcs_file INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) WHERE vf.commit_id = vc.id), ',') AS commit_files,
       array_to_string(array(SELECT vcs_file.full_filename FROM vcs_file INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) WHERE tdcabc.commit_id = vf.commit_id OR tdclbc.commit_id = vf.commit_id), ',') AS defect_closed_by_caused_by_commits_files,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) WHERE tdcabc.commit_id = vca.commit_id OR tdclbc.commit_id = vca.commit_id), ',') AS defect_closed_by_caused_by_commits_areas,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_area_dependencies v ON (vcs_area.id = v.to_area_id) INNER JOIN vcs_commit_areas vca ON (v.from_area_id = vca.area_id) WHERE tdcabc.commit_id = vca.commit_id OR tdclbc.commit_id = vca.commit_id), ',') AS defect_closed_by_caused_by_commits_dependent_areas,
       array_to_string(array(SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) WHERE tdclbc.commit_id = vca.commit_id INTERSECT SELECT vcs_area.name FROM vcs_area INNER JOIN vcs_commit_areas vca ON (vcs_area.id = vca.area_id) WHERE tdcabc.commit_id = vca.commit_id), ',') AS defect_closed_by_caused_by_intersection_areas,
       array_to_string(array(SELECT vcs_file.full_filename FROM vcs_file INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) WHERE tdclbc.commit_id = vf.commit_id INTERSECT SELECT vcs_file.full_filename FROM vcs_file INNER JOIN vcs_filechange vf ON (vcs_file.id = vf.file_id) WHERE tdcabc.commit_id = vf.commit_id), ',') AS defect_closed_by_caused_by_intersection_files
FROM testing_test
    INNER JOIN testing_testsuite_tests ttt ON (testing_test.id = ttt.test_id)
    INNER JOIN vcs_area va ON (testing_test.area_id = va.id)
    LEFT JOIN testing_testrunresult tt ON (testing_test.id = tt.test_id)
    LEFT JOIN vcs_commit vc on (tt.commit_id = vc.id)
    LEFT JOIN testing_defect commit_defect ON (tt.id = commit_defect.created_by_commit_id AND tt.test_run_id = commit_defect.created_by_test_run_id)
    LEFT JOIN testing_defect_caused_by_commits tdcabc ON (commit_defect.id = tdcabc.defect_id)
    LEFT JOIN testing_defect_closed_by_commits tdclbc ON (commit_defect.id = tdclbc.defect_id)
WHERE ttt.testsuite_id = {test_suite_id};
