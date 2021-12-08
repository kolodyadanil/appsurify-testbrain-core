# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import connection
# from .models import LicenseKey
#
#
# SQL_STATISTIC_TEMPLATE = """
# SELECT
#     ((count_passed_tests.count - avg_tests_per_runs.avg) * avg_tests_execution_time.avg * count_test_runs.count)::integer as count
# FROM
# (
#     SELECT coalesce(count(distinct ttrr1.test_id), 0) as count
#     FROM testing_testrunresult ttrr1
#     WHERE ttrr1.created >= CURRENT_DATE - INTERVAL '6 month'
#     AND ttrr1.status = 'pass'
#     AND ttrr1.test_suite_id = {test_suite_id}
# ) AS count_passed_tests,
# (
#     SELECT coalesce(avg(test_run_tests.count)::integer, 0) as avg
#     FROM (
#         SELECT count(DISTINCT ttrr2.test_id) as count
#         FROM testing_testrunresult ttrr2
#         WHERE date_trunc('month', ttrr2.created)::date = date_trunc('month', CURRENT_DATE)::date
#         AND ttrr2.test_suite_id = {test_suite_id}
#         GROUP BY ttrr2.test_run_id
#     ) AS test_run_tests
# ) AS avg_tests_per_runs,
# (
#     SELECT coalesce(avg(round_execution_time(ttrr3.execution_time))::integer, 0) as avg
#     FROM testing_testrunresult ttrr3
#     WHERE date_trunc('month', ttrr3.created)::date = date_trunc('month', CURRENT_DATE)::date
#     AND ttrr3.status = 'pass'
#     AND ttrr3.test_suite_id = {test_suite_id}
# ) AS avg_tests_execution_time,
# (
#     SELECT coalesce(count(DISTINCT ttrr3.test_run_id), 0) as count
#     FROM testing_testrunresult ttrr3
#     WHERE date_trunc('month', ttrr3.created)::date = date_trunc('month', CURRENT_DATE)::date
#     AND ttrr3.test_suite_id = {test_suite_id}
# ) AS count_test_runs
# LIMIT 1;
# """
#
#
# def load_data(sql):
#     cursor = connection.cursor()
#     cursor.execute(sql)
#     data = cursor.fetchone()[0]
#     return int(data)
#
#
# def get_usage(test_suite_id):
#     sql = SQL_STATISTIC_TEMPLATE.format(test_suite_id=test_suite_id)
#     data = load_data(sql)
#     return data
#
#
# def check_usage(organization, test_suite_id):
#     balance = LicenseKey.get_available_balance(organization=organization)
#     limit_count = balance
#
#     if limit_count == -1:
#         return False
#
#     count = get_usage(test_suite_id)
#     if count > limit_count:  # Need pay
#         return True
#     else:
#         return False
