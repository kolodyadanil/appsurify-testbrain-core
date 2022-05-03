# -*- coding: utf-8 -*-
import os
from collections import OrderedDict
from datetime import timedelta
import subprocess
import lxml.etree as ET
import defusedxml.ElementTree as dET
import xmltodict
from django.conf import settings
from django.db import transaction, models
from django.db.models import signals
from django.utils import timezone

from tempfile import mkstemp
from lxml.etree import XMLSyntaxError

from applications.testing.models import Test, TestSuite, TestRun, TestRunResult, Defect, TestReport
from applications.testing.signals import model_test_run_tests_changed, model_test_run_result_complete_test_run, \
    model_test_run_result_perform_defect
from applications.vcs.models import Area, ParentCommit

TYPE_NUNIT3 = 'nunit3'
TYPE_JUNIT = 'junit'
TYPE_TRX = 'trx'


ALLOWED_FORMAT_TYPES = [TYPE_JUNIT, TYPE_NUNIT3, TYPE_TRX]


def preprocessing_dict(xmldict):
    new_xmldict = dict()
    keys = xmldict.keys()
    for key in keys:
        if key[0] == '@':
            new_xmldict[key[1:]] = xmldict.get(key)
        else:
            new_xmldict[key] = xmldict.get(key)
    return new_xmldict


def preprocessing_area_dict(xmldict):
    new_xmldict = dict()
    keys = xmldict.keys()
    for key in keys:
        if key[0] == '@':
            new_xmldict[key[1:]] = xmldict.get(key)
        else:
            new_xmldict[key] = xmldict.get(key)
    return new_xmldict


def external_processor(xslt, source):
    xslt_fd, xslt_filename = mkstemp()
    xslt_file = open(xslt_filename, 'w')
    xslt_file.write(xslt)
    xslt_file.close()
    os.close(xslt_fd)

    source_fd, source_filename = mkstemp()
    source_file = open(source_filename, 'w')
    source_file.write(source)
    source_file.close()
    os.close(source_fd)

    commandLine = 'saxon -s:{source_filename} -xsl:{xslt_filename}'.format(
        source_filename=source_filename, xslt_filename=xslt_filename)
    process = subprocess.Popen(commandLine, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = process.stdout.read().strip()
    error = process.stderr.read().strip()
    if error:
        process.kill()
        raise Exception(error)
    return out


class ImportUtils(object):

    def __init__(self, type_xml, file_obj, data, user_id, test_run_name, host):
        self.type_xml = type_xml
        self.infile = file_obj.read()
        self.data = data
        self.user_id = user_id
        self.project = data.get('project')
        self.commit = data.get('commit', None)
        self.status = {
            'Unknown': TestRunResult.STATUS_UNKNOWN,
            'Passed': TestRunResult.STATUS_PASS,
            'Failed': TestRunResult.STATUS_FAIL,
            'Broken': TestRunResult.STATUS_BROKEN,
            'Not_run': TestRunResult.STATUS_NOT_RUN,
            'Skipped': TestRunResult.STATUS_SKIPPED,
            'Warning': TestRunResult.STATUS_WARNING,
            'Error': TestRunResult.STATUS_ERROR,
            'Pending': TestRunResult.STATUS_PENDING,
            'Canceled': TestRunResult.STATUS_CANCELED,
            'Other': TestRunResult.STATUS_OTHER,
            'Done': TestRunResult.STATUS_DONE,
        }
        self.failed_test = 0
        self.passed_test = 0
        self.broken_test = 0
        self.skipped_test = 0
        self.new_defects = 0
        self.flaky_defects = 0
        self.reopened_defects = 0
        self.reopened_flaky_defects = 0
        self.flaky_failures_breaks = 0
        self.host = host
        self.test_suite = data.get('test_suite')
        self.test_run_name = test_run_name
        self.test_run = None

        source = self.infile
        if isinstance(source, bytes):
            source = source.decode('utf-8', errors='replace')

        format = TestReport.Format.UNKNOWN
        if type_xml.upper() in TestReport.Format.values:
            format = TestReport.Format[type_xml.upper()]

        self.test_report = TestReport.objects.create(
            project=self.project,
            test_suite=self.test_suite,
            commit_sha=self.commit.sha,
            test_run_name=self.test_run_name,
            name=file_obj.name,
            source=source,
            destination="",
            format=format,
            status=TestReport.Status.PENDING
        )
        self.test_report.save()

    def import_xml_tests(self):
        self.test_report.status = TestReport.Status.PROCESSING
        self.test_report.save(update_fields=["status", "updated"])

        if self.type_xml == 'nunit3':
            xslt = ET.parse(os.path.join(settings.BASE_DIR, 'applications/testing/tools/nunit3-junit.xslt'))
            transform = ET.XSLT(xslt)
            dom = dET.fromstring(self.infile)
            new_dom = transform(dom)
            new_dom_str = ET.tostring(new_dom, pretty_print=True)
            infile = new_dom_str
        elif self.type_xml == 'trx':
            xslt = open(os.path.join(settings.BASE_DIR, 'applications/testing/tools/mstest-to-junit.xsl'), 'r').read()
            if isinstance(xslt, bytes):
                xslt = xslt.decode('utf-8', errors='replace')
            source = self.infile
            if isinstance(source, bytes):
                source = source.decode('utf-8', errors='replace')
            result = external_processor(xslt=xslt, source=source)
            if isinstance(result, bytes):
                result = result.decode('utf-8', errors='replace')
            infile = result

        elif self.type_xml == 'junit':
            infile = self.infile
            if isinstance(infile, bytes):
                infile = infile.decode('utf-8', errors='replace')

        else:
            self.test_report.status = TestReport.Status.FAILURE
            self.test_report.save(update_fields=["status", "updated"])
            return {"error": "Unknown report type."}

        try:
            xml_dict = xmltodict.parse(infile)
            if isinstance(infile, bytes):
                infile = infile.decode('utf-8', errors='replace')
            self.test_report.destination = infile
            self.test_report.save(update_fields=["destination", "updated"])
        except Exception as e:
            self.test_report.status = TestReport.Status.FAILURE
            self.test_report.save(update_fields=["status", "updated"])
            return {"error": "XML Parse error."}

        ts = self.data.get('test_suite', None)
        self.test_suite = TestSuite.objects.get(id=ts.id)

        root = xml_dict.get('testsuites', None)
        if root is None:
            root = xml_dict

        previous_testrun = None

        if self.test_run_name:
            self.test_run, created = TestRun.objects.get_or_create(project=self.project,
                                                                   test_suite=self.test_suite,
                                                                   name=self.test_run_name, meta=list())
        elif self.commit:
            self.test_run, created = TestRun.objects.get_or_create(project=self.project,
                                                                   test_suite=self.test_suite,
                                                                   name='{}_{}'.format(
                                                                       self.test_suite.name, self.commit.sha),
                                                                   meta=list())
        else:
            self.test_run = TestRun()
            self.test_run.project = self.data.get('project')
            self.test_run.meta = list()
            created = True

        if self.commit:
            try:
                parent_commit = ParentCommit.objects.filter(to_commit=self.commit).first()
                if parent_commit:
                    if parent_commit.from_commit.test_runs.exists():
                        previous_testrun = parent_commit.from_commit.test_runs.last()
            except ParentCommit.DoesNotExist:
                previous_testrun = None

        if created:
            self.test_run.author_id = self.user_id
            self.test_run.commit = self.commit
            self.test_run.previous_test_run = previous_testrun
            self.test_run.test_suite_id = self.test_suite.id
            self.test_run.type = TestRun.TYPE_COMMIT if self.commit else TestRun.TYPE_MANUAL

            self.test_run.save()

            if not self.test_run.name:
                self.test_run.name = 'TestRun_{}'.format(self.test_run.id)
                self.test_run.save()

        self.host += '{}'.format(self.test_run.id)

        old_defects = list(
            self.test_suite.created_defects.exclude(original_defect__isnull=False).exclude(
                type=Defect.TYPE_FLAKY).values_list('id', flat=True))
        old_flaky_defects = list(
            self.test_suite.founded_defects.filter(type=Defect.TYPE_FLAKY).values_list('id', flat=True))
        old_reopened_defects = list(self.test_suite.reopened_defects.exclude(type=Defect.TYPE_FLAKY
                                                                             ).values_list('id', flat=True))
        old_reopened_flaky_defects = list(
            self.test_suite.reopened_defects.filter(type=Defect.TYPE_FLAKY).values_list('id',
                                                                                        flat=True))
        old_failed_test = list(
            TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                         status=TestRunResult.STATUS_FAIL).exclude(
                created_defects__type=Defect.TYPE_FLAKY).values_list('id', flat=True))
        old_broken_test = list(
            TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                         status=TestRunResult.STATUS_BROKEN).exclude(
                created_defects__type=Defect.TYPE_FLAKY).values_list('id', flat=True))
        old_passed_test = list(
            TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                         status=TestRunResult.STATUS_PASS).exclude(
                created_defects__type=Defect.TYPE_FLAKY).values_list('id', flat=True))
        old_skipped_test = list(
            TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                         status=TestRunResult.STATUS_SKIPPED).exclude(
                created_defects__type=Defect.TYPE_FLAKY).values_list('id', flat=True))

        areas = root.get('testsuite', [])
        test_run_results = []

        if isinstance(areas, OrderedDict):
            areas = [areas]

        for area in areas:
            area = preprocessing_area_dict(area)
            area_obj, created = Area.objects.get_or_create(project=self.project, name=area.get('name')[:255])
            test_run_results = list()
            if isinstance(area.get('testcase'), OrderedDict):
                tests = self.prepare_tests([area.get('testcase')], area_obj)

                with transaction.atomic(using=TestRunResult.objects.db, savepoint=False):
                    test_run_results.append(self.create_test_case(area.get('testcase'), area_obj, tests))

            elif isinstance(area.get('testcase'), list):
                tests = self.prepare_tests(area.get('testcase'), area_obj)

                with transaction.atomic(using=TestRunResult.objects.db, savepoint=False):
                    for test_case in area.get('testcase'):
                        test_run_results.append(self.create_test_case(test_case, area_obj, tests))

            self.test_run_result_complete()

            for test_run_result in test_run_results:
                Defect.perform(test_run_result)

        self.new_defects = self.test_suite.created_defects.exclude(original_defect__isnull=False).exclude(
            type=Defect.TYPE_FLAKY).exclude(id__in=old_defects).count()

        self.flaky_defects = self.test_suite.founded_defects.filter(type=Defect.TYPE_FLAKY).exclude(
            id__in=old_flaky_defects).count()

        self.reopened_defects = self.test_suite.reopened_defects.exclude(
            type=Defect.TYPE_FLAKY).exclude(id__in=old_reopened_defects).count()

        self.reopened_flaky_defects = self.test_suite.reopened_defects.filter(
            type=Defect.TYPE_FLAKY).exclude(id__in=old_reopened_flaky_defects).count()

        self.flaky_failures_breaks = self.test_run.test_run_results.filter(
            models.Q(status=TestRunResult.STATUS_FAIL) | models.Q(status=TestRunResult.STATUS_BROKEN)).filter(
            models.Q(founded_defects__type=Defect.TYPE_FLAKY) & ~models.Q(founded_defects__status=Defect.STATUS_CLOSED)).count()

        self.failed_test = TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                                        status=TestRunResult.STATUS_FAIL).exclude(
            created_defects__type=Defect.TYPE_FLAKY).exclude(id__in=old_failed_test).count()

        self.broken_test = TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                                        status=TestRunResult.STATUS_BROKEN).exclude(
            created_defects__type=Defect.TYPE_FLAKY).exclude(id__in=old_broken_test).count()

        self.passed_test = TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                                        status=TestRunResult.STATUS_PASS).exclude(
            created_defects__type=Defect.TYPE_FLAKY).exclude(id__in=old_passed_test).count()

        self.skipped_test = TestRunResult.objects.filter(test_suite_id=self.test_suite.id, test_run_id=self.test_run.id,
                                                         status=TestRunResult.STATUS_SKIPPED).exclude(
            created_defects__type=Defect.TYPE_FLAKY).exclude(id__in=old_skipped_test).count()

        data = {
            'failed_tests': self.failed_test if self.failed_test >= 0 else 0,
            'new_defects': self.new_defects if self.new_defects >= 0 else 0,
            'flaky_defects': self.flaky_defects if self.flaky_defects >= 0 else 0,
            'reopened_defects': self.reopened_defects if self.reopened_defects >= 0 else 0,
            'broken_tests': self.broken_test if self.broken_test >= 0 else 0,
            'reopened_flaky_defects': self.reopened_flaky_defects if self.reopened_defects >= 0 else 0,
            'skipped_tests': self.skipped_test if self.skipped_test >= 0 else 0,
            'passed_tests': self.passed_test if self.passed_test >= 0 else 0,
            'flaky_failures_breaks': self.flaky_failures_breaks if self.flaky_failures_breaks >= 0 else 0,
            'report_url': self.host,
            'test_run_id': self.test_run.id,
        }

        self.test_report.status = TestReport.Status.SUCCESS
        self.test_report.save(update_fields=["status", "updated"])
        return data

    def test_run_result_complete(self):
        if not self.test_run.test_run_results.exclude(status=TestRunResult.STATUS_PENDING).exists():
            self.test_run.status = TestRun.STATUS_COMPLETE
            self.test_run.end_date = timezone.now()
            self.test_run.save()

            self.test_run.test_run_results.update(test_run_status=self.test_run.status,
                                                  test_run_end_date=self.test_run.end_date)

    def prepare_tests(self, testcase_json, area):
        class_names = {test_case.get('@name'): test_case.get('@classname', '') for test_case in testcase_json}
        test_cases_names = set(class_names.keys())
        testsuite_name = area.name
        tests = list(Test.objects.filter(area=area).values_list('name', flat=True))
        tests = set(tests)
        test_bulk_create = list()
        linked_areas = list(area.links.all())
        new_tests = test_cases_names - tests

        for test_case_name in new_tests:
            test = Test()
            test.project = self.project
            test.author_id = self.user_id
            test.name = test_case_name
            test.class_name = class_names[test_case_name]
            test.testsuite_name = testsuite_name
            test.type = Test.TYPE_AUTOMATIC
            test.tags = list()
            test.lines = list()
            test.parameters = list()
            test.meta = list()
            test.area = area

            test_bulk_create.append(test)

        Test.objects.bulk_create(test_bulk_create)
        for test in test_bulk_create:
            test.update_associated_areas_by_linked_areas(linked_areas)

        tests = list(Test.objects.filter(name__in=test_cases_names,
                                         area=area,
                                         project=self.project))

        signals.m2m_changed.disconnect(receiver=model_test_run_tests_changed, sender=TestRun.tests.through)
        self.test_run.tests.add(*tests)
        self.test_suite.tests.add(*tests)
        self.test_run.areas.add(area)
        signals.m2m_changed.connect(receiver=model_test_run_tests_changed, sender=TestRun.tests.through)

        return {test.name: test for test in tests}

    def create_test_case(self, testcase_json, area, tests):
        if not isinstance(testcase_json, OrderedDict):
            return {'error': 'Unknown error'}
        testcase_json = preprocessing_dict(testcase_json)

        name_test = testcase_json.get('name')

        test_run_result = TestRunResult()
        test_run_result.project = self.project
        test_run_result.test_type = self.test_suite.test_type
        test_run_result.test_suite = self.test_suite
        test_run_result.test_run = self.test_run
        test_run_result.area = area
        test_run_result.test = tests.get(name_test)
        test_run_result.commit = self.commit

        test_run_result.execution_ended = timezone.now()

        test_run_result_time = testcase_json.get('time', 0)
        if str(test_run_result_time).lower() == 'nan' or str(test_run_result_time) == '':
            test_run_result_time = 0

        test_run_result.execution_started = test_run_result.execution_ended - timedelta(
            seconds=float(test_run_result_time))

        test_run_result.meta = list()
        status = testcase_json.get('status', None)
        if status:
            test_run_result.status = self.status.get(status, 'Unknown')
        else:
            if 'failure' in testcase_json.keys():
                test_run_result.status = self.status.get('Failed')
                failure_dict = preprocessing_dict(testcase_json.get('failure'))
                test_run_result.stacktrace = failure_dict.get('#text') or str()
                test_run_result.failure_message = failure_dict.get('message', '')
                test_run_result.result = failure_dict.get('type', '')
            elif 'error' in testcase_json.keys():
                test_run_result.status = self.status.get('Broken')
                error_dict = preprocessing_dict(testcase_json.get('error'))
                test_run_result.stacktrace = error_dict.get('#text') or str()
                test_run_result.failure_message = error_dict.get('message', '')
                test_run_result.result = error_dict.get('type')
            elif 'skipped' in testcase_json.keys():
                test_run_result.status = self.status.get('Skipped')
                test_run_result.result = str()
                test_run_result.stacktrace = str()
                test_run_result.failure_message = str()
            else:
                test_run_result.status = self.status.get('Passed')
                test_run_result.result = str()
                test_run_result.stacktrace = str()
                test_run_result.failure_message = str()

        test_run_result.log = testcase_json.get('system-out', str())

        signals.post_save.disconnect(receiver=model_test_run_result_complete_test_run, sender=TestRunResult)
        signals.post_save.disconnect(receiver=model_test_run_result_perform_defect, sender=TestRunResult)
        test_run_result.save()
        signals.post_save.connect(receiver=model_test_run_result_complete_test_run, sender=TestRunResult)
        signals.post_save.connect(receiver=model_test_run_result_perform_defect, sender=TestRunResult)

        return test_run_result

