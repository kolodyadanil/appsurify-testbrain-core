# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import models
from django.db.models import functions
from django.db.models.functions import *
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.db import transaction, connection
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from applications.testing.tasks import add_caused_by_commits_task, add_closed_by_commits_task

try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text

from collections import Counter

User = get_user_model()


class TestReport(models.Model):

    class Format(models.TextChoices):
        UNKNOWN = "UNKNOWN", "UNKNOWN"
        NUNIT3 = "NUNIT3", "NUNIT3"
        JUNIT = "JUNIT", "JUNIT"
        TRX = "TRX", "TRX"

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        PROCESSING = "PROCESSING", "PROCESSING"
        SUCCESS = "SUCCESS", "SUCCESS"
        FAILURE = "FAILURE", "FAILURE"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    project = models.ForeignKey(
        "project.Project",
        related_name="test_reports",
        blank=False,
        null=False,
        on_delete=models.CASCADE
    )

    test_suite = models.ForeignKey(
        "testing.TestSuite",
        related_name="test_reports",
        blank=False,
        null=False,
        on_delete=models.CASCADE
    )

    test_run_name = models.CharField(
        max_length=255,
        blank=True,
        null=False
    )

    commit_sha = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        null=False
    )

    source = models.TextField(
        blank=False,
        null=False
    )

    destination = models.TextField(
        blank=True,
        null=False
    )

    format = models.CharField(
        verbose_name="format",
        max_length=128,
        default=Format.UNKNOWN,
        choices=Format.choices,
        blank=False,
        null=False
    )

    status = models.CharField(
        verbose_name="status",
        max_length=128,
        default=Status.UNKNOWN,
        choices=Status.choices,
        blank=False,
        null=False
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["-id", "-project", "-test_suite"]
        verbose_name = "test report"
        verbose_name_plural = "test reports"

    def __str__(self):
        return f"<TestReport: {self.id} (TestSuite: {self.test_suite_id})>"


class TestType(models.Model):
    """
    TestType object
    """

    project = models.ForeignKey("project.Project", related_name="test_types", blank=False, null=False,
                                on_delete=models.CASCADE)

    name = models.CharField(max_length=255, blank=False, null=False)

    rerun_all = models.BooleanField(default=True)
    rerun_flaky = models.BooleanField(default=True)

    number_of_reruns = models.IntegerField(default=1, blank=False, null=False)
    report_after_failure = models.BooleanField(default=True, blank=False, null=False)

    max_number_of_thread = models.IntegerField(default=1, blank=False, null=False)
    test_run_endpoint = models.CharField(max_length=255, blank=True, null=False)

    timeout = models.IntegerField(default=300, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        unique_together = ["project", "name", ]
        verbose_name = "test type"
        verbose_name_plural = "test types"

    def __str__(self):
        return f"<TestType: {self.id} ({self.name})>"

    @classmethod
    def get_default(cls, project):
        test_type, created = cls.objects.get_or_create(
            project=project,
            name="Default Test Type",
        )
        if created:
            test_type.rerun_all = True
            test_type.rerun_flaky = True
            test_type.number_of_reruns = 1
            test_type.report_after_failure = True
            test_type.max_number_of_thread = 1
            test_type.test_run_endpoint = ''
            test_type.timeout = 300
            test_type.save()

        return test_type


class Test(models.Model):
    TYPE_MANUAL = 1
    TYPE_AUTOMATIC = 2

    TYPE_CHOICE = (
        (TYPE_MANUAL, _(u'MANUAL')),
        (TYPE_AUTOMATIC, _(u'AUTOMATIC')),
    )

    project = models.ForeignKey('project.Project', related_name='tests', blank=False, null=False,
                                on_delete=models.CASCADE)

    area = models.ForeignKey('vcs.Area', related_name='tests', blank=True, null=True, on_delete=models.CASCADE)

    associated_files = models.ManyToManyField(
        "vcs.File",
        related_name="associated_files",
        blank=True,
        through="TestAssociatedFiles"
    )
    associated_areas = models.ManyToManyField(
        "vcs.Area",
        related_name="associated_areas",
        blank=True,
        through="TestAssociatedAreas"
    )

    author = models.ForeignKey(User, related_name='tests', blank=True, null=True, on_delete=models.CASCADE)

    name = models.CharField(max_length=1000, default='Test #', blank=True, null=True)
    mix_name = models.CharField(max_length=1000, blank=True, null=True)
    class_name = models.CharField(max_length=1000, blank=True, null=True)
    testsuite_name = models.CharField(max_length=1000, blank=True, null=True)
    description = models.TextField(max_length=4000, blank=True, null=True)

    # TODO: Fields for capabilities with 3rd party system
    extra_data = JSONField(default=dict, blank=True, null=False)

    type = models.IntegerField(choices=TYPE_CHOICE, default=TYPE_MANUAL, blank=False, null=False)

    steps = models.ManyToManyField('Step', through='TestStep', blank=True)

    tags = ArrayField(models.CharField(max_length=255), blank=True)
    lines = ArrayField(models.TextField(max_length=4000), blank=True)

    parameters = ArrayField(models.CharField(max_length=255), blank=True)
    meta = ArrayField(models.CharField(max_length=255), blank=True)

    priority = models.IntegerField(default=5, blank=False, null=False)
    usage = models.IntegerField(default=0, blank=False, null=False)

    timeout = models.IntegerField(default=300, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        verbose_name = _(u'test')
        verbose_name_plural = _(u'tests')

    def __unicode__(self):
        return u'{project} {name}'.format(project=self.project, name=self.name)

    def add_step(self, step, index_number):
        test_step, created = TestStep.objects.get_or_create(
            step=step,
            test=self,
            index_number=index_number)
        return test_step

    def remove_step(self, step, index_number):
        result = TestStep.objects.filter(
            step=step,
            test=self,
            index_number=index_number).delete()
        return result

    def get_current_test_run_results_status(self):
        newest_test_run_results = TestRunResult.objects.filter(test_suite__in=self.test_suites.all(),
                                                               test_run__in=self.test_runs.all(),
                                                               test=models.OuterRef('id')).order_by('-created')
        queryset = Test.objects.filter(id=self.id).annotate(
            current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1]),
            # previous_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[1:2:])
        )

        return queryset.values('current_test_run_results_status').first()['current_test_run_results_status']

    def get_previous_test_run_results_status(self):
        newest_test_run_results = TestRunResult.objects.filter(test_suite__in=self.test_suites.all(),
                                                               test_run__in=self.test_runs.all(),
                                                               test=models.OuterRef('id')).order_by('-created')

        queryset = Test.objects.filter(id=self.id).annotate(
            # current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1]),
            previous_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[1:2:])
        )

        return queryset.values('previous_test_run_results_status').first()['previous_test_run_results_status']

    def get_recently_test_runs(self):
        queryset = TestRun.objects.filter(
            test_suite__in=self.test_suites.all(), tests=self
        ).order_by('-created')[:10]
        return queryset

    @property
    def recently_test_runs(self):
        return self.get_recently_test_runs()

    def update_associated_areas_by_linked_areas(self, linked_areas=None):
        """
        Add in 'associated_areas' all areas that linked with area in 'area' field.

        :param linked_areas: this param should be used for optimization
        when we want update bunch of test for the same area.
        """
        if self.area is not None and linked_areas is None:
            linked_areas = list(self.area.links.all())
            self.associated_areas.add(*linked_areas)
        elif linked_areas:
            self.associated_areas.add(*linked_areas)


class TestStep(models.Model):
    """
    Test step model.
    """
    test = models.ForeignKey('Test', on_delete=models.CASCADE)
    step = models.ForeignKey('Step', on_delete=models.CASCADE)

    index_number = models.IntegerField(default=0, blank=False, null=False, db_index=True)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        ordering = ('index_number',)
        verbose_name = _(u'test step')
        verbose_name_plural = _(u'test steps')


class Step(models.Model):
    project = models.ForeignKey('project.Project', related_name='steps', blank=False, null=False,
                                on_delete=models.CASCADE)

    name = models.CharField(max_length=255, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        verbose_name = _(u'step')
        verbose_name_plural = _(u'steps')

    def __unicode__(self):
        return u'{id} | {name}'.format(id=self.id, name=self.name)


class TestSuite(models.Model):
    """
    Test Suite model.

    """
    TARGET_TYPE_COMMIT = 1
    TARGET_TYPE_TAG = 2

    TARGET_TYPE_CHOICE = (
        (TARGET_TYPE_COMMIT, 'commit'),
        (TARGET_TYPE_TAG, 'tag')
    )

    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(max_length=4000, blank=True, null=True)

    project = models.ForeignKey('project.Project', related_name='test_suites', on_delete=models.CASCADE)

    test_type = models.ForeignKey('TestType', related_name='test_suites', blank=True, null=True,
                                  on_delete=models.CASCADE)

    tests = models.ManyToManyField('Test', related_name='test_suites', blank=True)

    target_type = models.IntegerField(default=TARGET_TYPE_COMMIT, choices=TARGET_TYPE_CHOICE, blank=False, null=False)

    auto_raise_defect = models.BooleanField(default=True, blank=False, null=False)

    rerun_all = models.BooleanField(default=True, blank=False, null=False)
    rerun_flaky = models.BooleanField(default=True, blank=False, null=False)

    number_of_reruns = models.IntegerField(default=1, blank=False, null=False)
    auto_close_defect = models.BooleanField(default=True, blank=False, null=False)
    report_after_failure = models.BooleanField(default=True, blank=False, null=False)

    fail_fast = models.BooleanField(default=False, blank=False, null=False)

    test_suite_endpoint = models.CharField(max_length=255, default=str(), blank=True, null=True)
    location_of_tests = models.CharField(max_length=255, default=str(), blank=True, null=True)

    max_number_grouping = models.IntegerField(default=5, blank=False, null=False)

    priority = models.IntegerField(default=1, blank=False, null=False)
    prioritize_defect = models.BooleanField(default=False, blank=False, null=False)

    timeout = models.IntegerField(default=300)

    ml_model_last_time_created = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)


    class Meta(object):
        verbose_name = _(u'test suite')
        verbose_name_plural = _(u'test suites')

    def __str__(self):
        return f"<TestSuite: {self.id} ({self.name}) (Project: {self.project.name})>"

    @property
    def last_test_run(self):
        return self.test_runs.order_by('created').last()

    def auto_create_test_run(self, type, project=None, author=None, commit=None):
        current_test_run = self.test_runs.order_by('created').last()
        test_run = TestRun.objects.create(
            project=project,
            previous_test_run=current_test_run,
            author=author,
            test_suite=self,
            commit=commit,
            status=TestRun.STATUS_WAIT,
            type=type,
            meta=list()
        )

        tests = self.tests.filter(type=Test.TYPE_AUTOMATIC)
        test_run.tests.set(tests)
        test_run.save()
        return test_run


class TestRun(MPTTModel):
    TYPE_MANUAL = 1
    TYPE_COMMIT = 2
    TYPE_TAG = 3

    TYPE_CHOICE = (
        (TYPE_MANUAL, _(u'MANUAL')),
        (TYPE_COMMIT, _(u'COMMIT')),
        (TYPE_TAG, _(u'TAG')),
    )

    STATUS_WAIT = 1
    STATUS_IN_PROGRESS = 2
    STATUS_COMPLETE = 3

    STATUS_CHOICE = (
        (STATUS_WAIT, _(u'WAIT')),
        (STATUS_IN_PROGRESS, _(u'IN PROGRESS')),
        (STATUS_COMPLETE, _(u'COMPLETE')),
    )

    # previous_test_run = models.ForeignKey('self', blank=True, null=True)
    previous_test_run = TreeForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL)

    author = models.ForeignKey(User, related_name='test_runs', blank=True, null=True, on_delete=models.CASCADE)

    project = models.ForeignKey('project.Project', related_name='test_runs', blank=False, null=True,
                                on_delete=models.CASCADE)

    areas = models.ManyToManyField('vcs.Area', related_name='test_runs', blank=True)

    commit = models.ForeignKey('vcs.Commit', related_name='test_runs', blank=True, null=True,
                               on_delete=models.CASCADE)

    test_suite = models.ForeignKey('TestSuite', related_name='test_runs', blank=False, null=False,
                                   on_delete=models.CASCADE)

    tests = models.ManyToManyField('Test', related_name='test_runs', blank=True)

    name = models.CharField(max_length=1000, blank=True, null=True)
    description = models.TextField(max_length=4000, blank=True, null=True)

    meta = ArrayField(models.CharField(max_length=255), blank=True)

    # TODO: Fields for capabilities with 3rd party system
    extra_data = JSONField(default=dict, blank=True, null=False)

    type = models.IntegerField(choices=TYPE_CHOICE, default=TYPE_MANUAL, blank=False, null=False)
    status = models.IntegerField(choices=STATUS_CHOICE, default=STATUS_WAIT, blank=False, null=False)

    start_date = models.DateTimeField(auto_now_add=True, db_index=True)
    end_date = models.DateTimeField(blank=True, null=True, db_index=True)

    is_local = models.BooleanField(default=False, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        ordering = ('-id',)
        verbose_name = _(u'test run')
        verbose_name_plural = _(u'test runs')

    class MPTTMeta(object):
        parent_attr = 'previous_test_run'

    def __unicode__(self):
        return u'{id} {name} {status}'.format(id=self.id, name=self.name, status=self.get_status_display())

    @property
    def test_count(self):
        return self.tests.count()

    @property
    def execution_time(self):
        aggregate_data = self.test_run_results.aggregate(
            sum_execution=functions.Coalesce(models.Sum('execution_time'), 0, output_field=models.FloatField()))
        return aggregate_data['sum_execution']

    @property
    def execution_time_avg(self):
        aggregate_data = self.test_run_results.aggregate(
            avg_execution=functions.Coalesce(models.Avg('execution_time'), 0, output_field=models.FloatField()))
        return aggregate_data['avg_execution']

    @property
    def number_of_fail_results(self):
        newest_current_test_run_results = TestRunResult.objects.filter(
            test_run=self, area__in=self.areas.all(), test=models.OuterRef('id')).order_by('-created')

        queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(
                newest_current_test_run_results.values('status')[:1])).filter(
            current_test_run_results_status=TestRunResult.STATUS_FAIL)

        return queryset.count()

    @property
    def percentage_of_flaky_failure_results(self):
        newest_current_test_run_results = TestRunResult.objects.filter(
            test_run=self, area__in=self.areas.all(), test=models.OuterRef('id')).order_by('-created')

        queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=self)
            )
        ).count()

        try:
            return queryset * 100 / self.test_count
        except:
            return 0

    @property
    def test_run_results_summary(self):
        return self._get_test_run_results_summary()

    def generate_name(self):
        name = self.name
        if name is None or name == '':
            if self.commit is not None:
                name = self.commit.display_id
        return name

    def create_pending_test_run_results(self):
        test_run_results = list()

        test_queryset = self.tests.all()
        for test in test_queryset:
            if test.steps.all().exists():
                for step in test.teststep_set.all():
                    tr = TestRunResult(
                        project=self.project,
                        project_name=self.project.name,

                        test_type=self.test_suite.test_type,
                        test_type_name=self.test_suite.test_type.name,

                        test_suite=self.test_suite,
                        test_suite_name=self.test_suite.name,
                        test_suite_target_type=self.test_suite.target_type,
                        test_suite_created=self.test_suite.created,
                        test_suite_updated=self.test_suite.updated,

                        test_run=self,
                        test_run_name=self.name,
                        test_run_type=self.type,
                        test_run_status=self.status,
                        test_run_is_local=self.is_local,
                        test_run_start_date=self.start_date,
                        test_run_end_date=self.end_date,
                        test_run_created=self.created,
                        test_run_updated=self.updated,

                        area=test.area,
                        area_name=test.area.name,
                        area_created=test.area.created,
                        area_updated=test.area.updated,

                        test=test,
                        test_name=test.name,
                        test_created=test.created,
                        test_updated=test.updated,

                        step=step.step,
                        step_name=step.step.name,
                        step_index_number=step.index_number,
                        result=str(),
                        stacktrace=str(),
                        failure_message=str(),
                        log=str(),
                        meta=list(),
                        status=TestRunResult.STATUS_PENDING,
                        is_local=self.is_local
                    )
                    if self.commit is not None:
                        tr.commit = self.commit
                        tr.commit_timestamp = self.commit.timestamp
                        tr.commit_display_id = self.commit.display_id
                        tr.commit_created = self.commit.created
                        tr.commit_updated = self.commit.updated

                    test_run_results.append(tr)
            else:
                tr = TestRunResult(
                    project=self.project,
                    project_name=self.project.name,

                    test_type=self.test_suite.test_type,
                    test_type_name=self.test_suite.test_type.name,

                    test_suite=self.test_suite,
                    test_suite_name=self.test_suite.name,
                    test_suite_target_type=self.test_suite.target_type,
                    test_suite_created=self.test_suite.created,
                    test_suite_updated=self.test_suite.updated,

                    test_run=self,
                    test_run_name=self.name,
                    test_run_type=self.type,
                    test_run_status=self.status,
                    test_run_is_local=self.is_local,
                    test_run_start_date=self.start_date,
                    test_run_end_date=self.end_date,
                    test_run_created=self.created,
                    test_run_updated=self.updated,

                    area=test.area,
                    area_name=test.area.name,
                    area_created=test.area.created,
                    area_updated=test.area.updated,

                    test=test,
                    test_name=test.name,
                    test_created=test.created,
                    test_updated=test.updated,

                    result=str(),
                    stacktrace=str(),
                    failure_message=str(),
                    log=str(),
                    meta=list(),
                    status=TestRunResult.STATUS_PENDING,
                    is_local=self.is_local
                )

                if self.commit is not None:
                    tr.commit = self.commit
                    tr.commit_timestamp = self.commit.timestamp
                    tr.commit_display_id = self.commit.display_id
                    tr.commit_created = self.commit.created
                    tr.commit_updated = self.commit.updated

                test_run_results.append(tr)

        test_run_results_queryset = TestRunResult.objects.bulk_create(test_run_results)
        return test_run_results_queryset

    def _current_test_run_results(self):
        newest_test_run_results = TestRunResult.objects.filter(test_run=self, test=models.OuterRef('id')).order_by(
            '-created')
        queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1])
        )
        d = Counter([x for x in queryset.values_list('current_test_run_results_status', flat=True)])
        return d

    def _get_test_run_results_summary(self):
        newest_current_test_run_results = TestRunResult.objects.filter(
            test_run=self, area__in=self.areas.all(), test=models.OuterRef('id')).order_by('-created')

        # TODO: FLAKY GROUP
        flaky_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=self)
        )

        flaky_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=self)
            )
            | models.Q(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=self.previous_test_run)
            )
        )

        flaky_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=self)
        )

        flaky_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                          TestRunResult.STATUS_SKIPPED]) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=self)
        )

        # TODO: INVALID TEST GROUP
        invalid_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
            models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
            ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
        )

        invalid_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
            models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
            ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
        )

        invalid_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
            models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
            ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
        )

        invalid_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                          TestRunResult.STATUS_SKIPPED]) &
            models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
            ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
        )

        # TODO: OPEN DEFECT GROUP
        open_defect_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
            models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
            ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
        )

        open_defect_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
            models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
            ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
        )

        open_defect_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
            models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
            ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
        )

        open_defect_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                          TestRunResult.STATUS_SKIPPED]) &
            models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
            ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
        )

        # TODO: READY FOR TEST GROUP
        ready_defect_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
            models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
            models.Q(associated_defects__status=Defect.STATUS_READY)
        )

        ready_defect_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
            models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
            models.Q(associated_defects__status=Defect.STATUS_READY)
        )

        ready_defect_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
            models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
            models.Q(associated_defects__status=Defect.STATUS_READY)
        )

        ready_defect_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).filter(
            models.Q(current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                          TestRunResult.STATUS_SKIPPED]) &
            models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
            models.Q(associated_defects__status=Defect.STATUS_READY)
        )

        # TODO: PASSED GROUP
        passed_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).exclude(
            models.Q(id__in=[id for id in flaky_test_passed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in invalid_test_passed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in open_defect_test_passed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in ready_defect_test_passed_test_run_result_queryset.values_list('id', flat=True)])
        ).filter(models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS))

        passed_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).exclude(
            models.Q(id__in=[id for id in flaky_test_failed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in invalid_test_failed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in open_defect_test_failed_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in ready_defect_test_failed_test_run_result_queryset.values_list('id', flat=True)])
        ).filter(models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL))

        passed_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).exclude(
            models.Q(id__in=[id for id in flaky_test_broken_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in invalid_test_broken_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in open_defect_test_broken_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in ready_defect_test_broken_test_run_result_queryset.values_list('id', flat=True)])
        ).filter(models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN))

        passed_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
        ).exclude(
            models.Q(id__in=[id for id in flaky_test_not_run_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(id__in=[id for id in invalid_test_not_run_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in open_defect_test_not_run_test_run_result_queryset.values_list('id', flat=True)]) |
            models.Q(
                id__in=[id for id in ready_defect_test_not_run_test_run_result_queryset.values_list('id', flat=True)])
        ).filter(models.Q(
            current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                 TestRunResult.STATUS_SKIPPED]))

        # TODO: TOTAL GROUP
        total_test_passed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(
                newest_current_test_run_results.values('status')[:1])).filter(
            current_test_run_results_status=TestRunResult.STATUS_PASS)
        total_test_failed_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(
                newest_current_test_run_results.values('status')[:1])).filter(
            current_test_run_results_status=TestRunResult.STATUS_FAIL)
        total_test_broken_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(
                newest_current_test_run_results.values('status')[:1])).filter(
            current_test_run_results_status=TestRunResult.STATUS_BROKEN)
        total_test_not_run_test_run_result_queryset = self.tests.annotate(
            current_test_run_results_status=models.Subquery(
                newest_current_test_run_results.values('status')[:1])).filter(
            current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                 TestRunResult.STATUS_SKIPPED])

        return dict(
            actual=dict(
                flaky_test_count=dict(
                    passed=flaky_test_passed_test_run_result_queryset.count(),
                    failed=flaky_test_failed_test_run_result_queryset.count(),
                    broken=flaky_test_broken_test_run_result_queryset.count(),
                    not_run=flaky_test_not_run_test_run_result_queryset.count()
                ),
                invalid_test_count=dict(
                    passed=invalid_test_passed_test_run_result_queryset.count(),
                    failed=invalid_test_failed_test_run_result_queryset.count(),
                    broken=invalid_test_broken_test_run_result_queryset.count(),
                    not_run=invalid_test_not_run_test_run_result_queryset.count()
                ),
                open_defect_test_count=dict(
                    passed=open_defect_test_passed_test_run_result_queryset.count(),
                    failed=open_defect_test_failed_test_run_result_queryset.count(),
                    broken=open_defect_test_broken_test_run_result_queryset.count(),
                    not_run=open_defect_test_not_run_test_run_result_queryset.count()
                ),
                ready_defect_test_count=dict(
                    passed=ready_defect_test_passed_test_run_result_queryset.count(),
                    failed=ready_defect_test_failed_test_run_result_queryset.count(),
                    broken=ready_defect_test_broken_test_run_result_queryset.count(),
                    not_run=ready_defect_test_not_run_test_run_result_queryset.count()
                ),
                passed_test_count=dict(
                    passed=passed_test_passed_test_run_result_queryset.count(),
                    failed=passed_test_failed_test_run_result_queryset.count(),
                    broken=passed_test_broken_test_run_result_queryset.count(),
                    not_run=passed_test_not_run_test_run_result_queryset.count()
                ),
                total_test_count=dict(
                    passed=total_test_passed_test_run_result_queryset.count(),
                    failed=total_test_failed_test_run_result_queryset.count(),
                    broken=total_test_broken_test_run_result_queryset.count(),
                    not_run=total_test_not_run_test_run_result_queryset.count()
                )
            )
        )


class TestRunMaterializedModel(models.Model):
    test_run = models.OneToOneField('testing.TestRun',
                                    related_name='mv_test_count_by_type', on_delete=models.CASCADE, primary_key=True)
    tests_count = models.IntegerField()
    passed_tests_count = models.IntegerField()
    skipped_tests_count = models.IntegerField()
    failed_tests_count = models.IntegerField()
    broken_tests_count = models.IntegerField()
    not_run_tests_count = models.IntegerField()
    execution_time = models.FloatField()
    status = models.CharField(max_length=16)

    class Meta(object):
        managed = False
        db_table = 'mv_test_count_by_type'

    @staticmethod
    @transaction.atomic
    def refresh():
        sql = f"""REFRESH MATERIALIZED VIEW mv_test_count_by_type;"""
        with connection.cursor() as cursor:
            cursor.execute(sql)


class TestRunResult(models.Model):
    STATUS_UNKNOWN = u'unknown'
    STATUS_PASS = u'pass'
    STATUS_FAIL = u'fail'
    STATUS_BROKEN = u'broken'
    STATUS_NOT_RUN = u'not_run'
    STATUS_SKIPPED = u'skipped'
    STATUS_WARNING = u'warning'
    STATUS_ERROR = u'error'
    STATUS_PENDING = u'pending'
    STATUS_CANCELED = u'canceled'
    STATUS_OTHER = u'other'
    STATUS_DONE = u'done'

    STATUS_CHOICE = (
        (STATUS_UNKNOWN, _(u'UNKNOWN')),
        (STATUS_PASS, _(u'PASS')),
        (STATUS_FAIL, _(u'FAIL')),
        (STATUS_BROKEN, _(u'BROKEN')),
        (STATUS_NOT_RUN, _(u'NOT RUN - not use')),
        (STATUS_SKIPPED, _(u'SKIPPED')),
        (STATUS_WARNING, _(u'WARNING')),
        (STATUS_ERROR, _(u'ERROR')),
        (STATUS_PENDING, _(u'PENDING')),
        (STATUS_CANCELED, _(u'CANCELED')),
        (STATUS_OTHER, _(u'OTHER')),
        (STATUS_DONE, _(u'DONE')),
    )

    project = models.ForeignKey('project.Project', related_name='test_run_results', blank=False, null=False,
                                on_delete=models.CASCADE)
    project_name = models.CharField(max_length=200, blank=False, null=False)

    test_type = models.ForeignKey('TestType', related_name='test_run_results', blank=False, null=False,
                                  on_delete=models.CASCADE)
    test_type_name = models.CharField(max_length=200, blank=False, null=False)

    test_suite = models.ForeignKey('TestSuite', related_name='test_run_results', blank=False, null=False,
                                   on_delete=models.CASCADE)
    test_suite_name = models.CharField(max_length=255, blank=False, null=False)
    test_suite_target_type = models.IntegerField(default=TestSuite.TARGET_TYPE_COMMIT)
    test_suite_created = models.DateTimeField(blank=False, null=False, db_index=True)
    test_suite_updated = models.DateTimeField(blank=False, null=False, db_index=True)

    test_run = models.ForeignKey('TestRun', related_name='test_run_results', blank=False, null=False,
                                 on_delete=models.CASCADE)
    test_run_name = models.CharField(max_length=255, blank=False, null=False)
    test_run_type = models.IntegerField(default=TestRun.TYPE_MANUAL, blank=False, null=False)
    test_run_status = models.IntegerField(default=TestRun.STATUS_WAIT, blank=False, null=False)
    test_run_is_local = models.BooleanField(default=False)
    test_run_start_date = models.DateTimeField(blank=False, null=False, db_index=True)
    test_run_end_date = models.DateTimeField(blank=True, null=True, db_index=True)
    test_run_created = models.DateTimeField(blank=False, null=False, db_index=True)
    test_run_updated = models.DateTimeField(blank=False, null=False, db_index=True)

    area = models.ForeignKey('vcs.Area', related_name='test_run_results', blank=True, null=True,
                             on_delete=models.CASCADE)
    area_name = models.CharField(max_length=255, blank=True, null=True)
    area_created = models.DateTimeField(blank=True, null=True, db_index=True)
    area_updated = models.DateTimeField(blank=True, null=True, db_index=True)

    test = models.ForeignKey('Test', related_name='test_run_results', blank=False, null=False,
                             on_delete=models.CASCADE)
    test_name = models.CharField(max_length=1000, blank=False, null=False)
    test_created = models.DateTimeField(blank=False, null=False, db_index=True)
    test_updated = models.DateTimeField(blank=False, null=False, db_index=True)

    step = models.ForeignKey('Step', related_name='test_run_results', blank=True, null=True,
                             on_delete=models.CASCADE)
    step_name = models.CharField(max_length=255, blank=True, null=True)
    step_index_number = models.IntegerField(default=0, blank=True, null=True)

    commit = models.ForeignKey('vcs.Commit', related_name='test_run_results', blank=True, null=True,
                               on_delete=models.CASCADE)
    commit_timestamp = models.DateTimeField(default=timezone.now, blank=False, null=False)
    commit_display_id = models.CharField(max_length=255, blank=True, null=True)
    commit_created = models.DateTimeField(blank=True, null=True, db_index=True)
    commit_updated = models.DateTimeField(blank=True, null=True, db_index=True)

    execution_started = models.DateTimeField(blank=True, null=True, db_index=True)
    execution_ended = models.DateTimeField(blank=True, null=True, db_index=True)
    execution_time = models.FloatField(default=float(), blank=False, null=False)

    is_local = models.BooleanField(default=False, blank=False, null=False)
    status = models.CharField(max_length=255, choices=STATUS_CHOICE, default=STATUS_UNKNOWN, blank=False, null=False,
                              db_index=True)
    meta = ArrayField(models.CharField(default=list, max_length=255), blank=True, null=True)

    result = models.CharField(max_length=255, blank=True)
    stacktrace = models.TextField(max_length=16000, blank=True)
    failure_message = models.TextField(max_length=4000, blank=True)
    log = models.TextField(max_length=16000, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        verbose_name = _(u'test run result')
        verbose_name_plural = _(u'test run results')
        indexes = [
            models.Index(fields=['-created'], name='testrunresult_created_idx'),
        ]

    def __unicode__(self):
        return u'{id} {result} {status}'.format(id=self.id, result=self.result, status=self.status)

    def get_execution_time(self):
        execution_time = float()

        if self.execution_started is not None and self.execution_ended is not None:
            try:
                execution_time = (self.execution_ended - self.execution_started).total_seconds()
            except Exception:
                execution_time = float()
        return execution_time


class TestRunResultAttachment(models.Model):
    project = models.ForeignKey('project.Project', related_name='test_run_result_attachments', blank=False, null=False,
                                on_delete=models.CASCADE)

    test_suite = models.ForeignKey('TestSuite', related_name='test_run_result_attachments', blank=False, null=False,
                                   on_delete=models.CASCADE)
    test_run = models.ForeignKey('TestRun', related_name='test_run_result_attachments', blank=False, null=False,
                                 on_delete=models.CASCADE)

    test_run_result = models.ForeignKey('TestRunResult', related_name='test_run_result_attachments', blank=False,
                                        null=False, on_delete=models.CASCADE)

    name = models.CharField(max_length=255, blank=False, null=False)

    order = models.IntegerField(default=0, blank=False, null=False)

    file = models.FileField(upload_to='uploads', blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        verbose_name = _(u'test run result attachment')
        verbose_name_plural = _(u'test run result attachments')

    def __unicode__(self):
        return u'{id} {name}'.format(id=self.id, name=self.name)


class Defect(models.Model):
    CREATE_TYPE_MANUAL = 1
    CREATE_TYPE_AUTOMATIC = 2
    CREATE_TYPE_GIT_IMPORT = 3

    CREATE_TYPE_CHOICE = (
        (CREATE_TYPE_MANUAL, _(u'MANUAL')),
        (CREATE_TYPE_AUTOMATIC, _(u'AUTOMATIC')),
        (CREATE_TYPE_GIT_IMPORT, _(u'GIT_IMPORT')),
    )

    TYPE_ENVIRONMENTAL = 1
    TYPE_FLAKY = 2
    TYPE_PROJECT = 3
    TYPE_INVALID_TEST = 4
    TYPE_LOCAL = 5
    TYPE_OUTSIDE = 6
    TYPE_NEW_TEST = 7

    TYPE_CHOICE = (
        (TYPE_ENVIRONMENTAL, _(u'ENVIRONMENTAL')),
        (TYPE_FLAKY, _(u'FLAKY')),
        (TYPE_PROJECT, _(u'PROJECT')),
        (TYPE_INVALID_TEST, _(u'INVALID TEST')),
        (TYPE_LOCAL, _(u'LOCAL')),
        (TYPE_OUTSIDE, _(u'OUTSIDE SCOPE')),
        (TYPE_NEW_TEST, _(u'NEW TEST')),
    )

    STATUS_NEW = 1
    STATUS_IN_PROGRESS = 2
    STATUS_READY = 3
    STATUS_CLOSED = 4
    STATUS_VERIFIED = 5

    STATUS_CHOICE = (
        (STATUS_NEW, _(u'NEW')),
        (STATUS_IN_PROGRESS, _(u'IN PROGRESS')),
        (STATUS_READY, _(u'READY')),
        (STATUS_CLOSED, _(u'CLOSED')),
        (STATUS_VERIFIED, _(u'VERIFIED')),
    )

    SEVERITY_TRIVIAL = 1
    SEVERITY_MINOR = 2
    SEVERITY_MAJOR = 3
    SEVERITY_CRITICAL = 4

    SEVERITY_CHOICE = (
        (SEVERITY_CRITICAL, _(u'CRITICAL')),
        (SEVERITY_MAJOR, _('MAJOR')),
        (SEVERITY_MINOR, _('MINOR')),
        (SEVERITY_TRIVIAL, _('TRIVIAL')),
    )

    CLOSE_TYPE_FIXED = 1
    CLOSE_TYPE_DUPLICATE = 2
    CLOSE_TYPE_WONT_FIX = 3
    CLOSE_TYPE_UNABLE_TO_REPRODUCE = 4
    CLOSE_TYPE_NOT_A_BUG = 5

    CLOSE_TYPE_CHOICE = (
        (CLOSE_TYPE_FIXED, _('FIXED')),
        (CLOSE_TYPE_DUPLICATE, _('DUPLICATE')),
        (CLOSE_TYPE_WONT_FIX, _('WON\'T FIX')),
        (CLOSE_TYPE_UNABLE_TO_REPRODUCE, _('UNABLE TO REPRODUCE')),
        (CLOSE_TYPE_NOT_A_BUG, _('NOT A BUG')),
    )

    project = models.ForeignKey('project.Project', related_name='defects', blank=False, null=False,
                                on_delete=models.CASCADE)
    owner = models.ForeignKey(User, related_name='owned_defects', blank=True, null=True, on_delete=models.CASCADE)
    # watchers = models.ManyToManyField(User, related_name='watched_defects', blank=True)

    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(max_length=4000, blank=True, null=True)

    reason = models.CharField(max_length=255, blank=False, null=False)
    error = models.TextField(max_length=4000, blank=False, null=False)
    matching = models.CharField(max_length=255, blank=True, null=False)

    type = models.IntegerField(choices=TYPE_CHOICE, default=TYPE_ENVIRONMENTAL, blank=False, null=False)
    create_type = models.IntegerField(choices=CREATE_TYPE_CHOICE, default=CREATE_TYPE_MANUAL, blank=False, null=False)

    close_type = models.IntegerField(choices=CLOSE_TYPE_CHOICE, blank=True, null=True)
    close_reason = models.CharField(max_length=255, default=str(), blank=True, null=False)

    status = models.IntegerField(choices=STATUS_CHOICE, default=STATUS_NEW, blank=False, null=False)
    severity = models.IntegerField(choices=SEVERITY_CHOICE, default=SEVERITY_TRIVIAL, blank=False, null=False)
    priority = models.IntegerField(default=1, blank=False, null=False)

    discovery_phase = models.CharField(max_length=255, blank=True, null=False)
    discovery_method = models.CharField(max_length=255, blank=True, null=False)
    origination_phase = models.CharField(max_length=255, blank=True, null=False)
    root_cause = models.CharField(max_length=255, blank=True, null=False)

    resolution_type = models.CharField(max_length=255, blank=True, null=False)
    leakage_reason = models.CharField(max_length=255, blank=True, null=False)

    found_date = models.DateTimeField(default=timezone.now, blank=False, null=False, db_index=True)
    reopen_date = models.DateTimeField(blank=True, null=True, db_index=True)
    close_date = models.DateTimeField(blank=True, null=True, db_index=True)

    # TODO: related fields
    associated_tests = models.ManyToManyField('Test', related_name='associated_defects', blank=True)

    # TODO: Link to objects in which defects are found
    found_test_suites = models.ManyToManyField('TestSuite', related_name='founded_defects', blank=True)
    found_test_runs = models.ManyToManyField('TestRun', related_name='founded_defects', blank=True)
    found_test_run_results = models.ManyToManyField('TestRunResult', related_name='founded_defects', blank=True)
    found_tests = models.ManyToManyField('Test', related_name='founded_defects', blank=True)
    found_commits = models.ManyToManyField('vcs.Commit', related_name='founded_defects', blank=True)

    # TODO: Link to objects in which defects are caused
    caused_by_test_suites = models.ManyToManyField('TestSuite', related_name='caused_defects', blank=True)
    caused_by_test_runs = models.ManyToManyField('TestRun', related_name='caused_defects', blank=True)
    caused_by_test_run_results = models.ManyToManyField('TestRunResult', related_name='caused_defects', blank=True)
    caused_by_tests = models.ManyToManyField('Test', related_name='caused_defects', blank=True)

    caused_by_commits = models.ManyToManyField(
        "vcs.Commit",
        related_name="caused_defects",
        blank=True,
        through="DefectCausedByCommits"
    )

    # TODO: Link to objects in which defects are reopen (who init reopen defect)
    reopen_test_suites = models.ManyToManyField('TestSuite', related_name='reopened_defects', blank=True)
    reopen_test_runs = models.ManyToManyField('TestRun', related_name='reopened_defects', blank=True)
    reopen_test_run_results = models.ManyToManyField('TestRunResult', related_name='reopened_defects', blank=True)
    reopen_tests = models.ManyToManyField('Test', related_name='reopened_defects', blank=True)
    reopen_commits = models.ManyToManyField('vcs.Commit', related_name='reopened_defects', blank=True)
    original_defect = models.ForeignKey('self', related_name='reopened_defect', blank=True, null=True,
                                        on_delete=models.CASCADE)

    # TODO: Link to objects in which defects are created (who init this defect)
    created_by_test_suite = models.ForeignKey('TestSuite', related_name='created_defects', blank=True, null=True,
                                              on_delete=models.CASCADE)
    created_by_test_run = models.ForeignKey('TestRun', related_name='created_defects', blank=True, null=True,
                                            on_delete=models.CASCADE)
    created_by_test_run_result = models.ForeignKey('TestRunResult', related_name='created_defects', blank=True,
                                                   null=True, on_delete=models.CASCADE)
    created_by_test = models.ForeignKey('Test', related_name='created_defects', blank=True, null=True,
                                        on_delete=models.CASCADE)
    created_by_commit = models.ForeignKey('vcs.Commit', related_name='created_defects', blank=True, null=True,
                                          on_delete=models.CASCADE)

    # TODO: Link to objects in which defects are closed (who init closed defect)
    closed_test_suite = models.ForeignKey('TestSuite', related_name='closed_defects', blank=True, null=True,
                                          on_delete=models.CASCADE)
    closed_test_run = models.ForeignKey('TestRun', related_name='closed_defects', blank=True, null=True,
                                        on_delete=models.CASCADE)
    closed_test_run_result = models.ForeignKey('TestRunResult', related_name='closed_defects', blank=True, null=True,
                                               on_delete=models.CASCADE)
    closed_test = models.ForeignKey('Test', related_name='closed_defects', blank=True, null=True,
                                    on_delete=models.CASCADE)
    closed_commit = models.ForeignKey('vcs.Commit', related_name='closed_defects', blank=True, null=True,
                                      on_delete=models.CASCADE)
    closed_by_commits = models.ManyToManyField(
        "vcs.Commit",
        related_name="closed_by_defects",
        blank=True,
        through="DefectClosedByCommits"
    )

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta(object):
        verbose_name = _(u'Defect')
        verbose_name_plural = _(u'Defects')

    def __unicode__(self):
        return u'{id} ({name})'.format(id=self.id, name=self.name)

    def build_absolute_url(self):
        from applications.allauth.account import app_settings as account_settings
        site = self.project.organization.site
        url = '/projects/{project_pk}/defects/{defect_pk}'.format(project_pk=self.project_id, defect_pk=self.id)
        ret = '{proto}://{domain}{url}'.format(
            proto=account_settings.DEFAULT_HTTP_PROTOCOL,
            domain=site.domain,
            url=url)
        return ret

    def format_email_subject(self, subject):
        site = self.project.organization.site
        prefix = "[{name}] ".format(name=site.name)
        return prefix + force_text(subject)

    def render_mail(self, template_prefix, email, context):
        """
        Renders an e-mail to `email`.  `template_prefix` identifies the
        e-mail that is to be sent, e.g. "testing/email/email_defect"
        """

        subject = render_to_string('{0}_subject.txt'.format(template_prefix), context)
        # remove superfluous line breaks
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        from_email = settings.DEFAULT_FROM_EMAIL

        bodies = {}
        for ext in ['html', 'txt']:
            try:
                template_name = '{0}_message.{1}'.format(template_prefix, ext)
                bodies[ext] = render_to_string(template_name, context).strip()
            except TemplateDoesNotExist:
                if ext == 'txt' and not bodies:
                    # We need at least one body
                    raise
        if 'txt' in bodies:
            msg = EmailMultiAlternatives(subject, bodies['txt'], from_email, [email])
            if 'html' in bodies:
                msg.attach_alternative(bodies['html'], 'text/html')
        else:
            msg = EmailMessage(subject, bodies['html'], from_email, [email])
            msg.content_subtype = 'html'  # Main content is now text/html
        return msg

    def send_mail(self, template_prefix, email, context):
        # msg = self.render_mail(template_prefix, email, context)
        # msg.send()
        pass

    def send_notification_mail(self, open=False, close=False, reopen=False, **kwargs):

        if open:
            template_prefix = 'testing/email/email_defect_open'
        elif close:
            template_prefix = 'testing/email/email_defect_close'
        elif reopen:
            template_prefix = 'testing/email/email_defect_reopen'
        else:
            template_prefix = 'testing/email/email_defect'

        if self.owner:
            email = self.owner.email
            defect_url = self.build_absolute_url()  # ex. /projects/1/defects/2

            ctx = {
                'user': self.owner,
                'project': self.project,
                'defect': self,
                'defect_url': defect_url
            }

            self.send_mail(template_prefix, email, ctx)

    @classmethod
    def get_severity_summary(cls, queryset=None):

        if queryset is None:
            queryset = cls.objects.all()

        severity_summary = queryset.aggregate(
            critical=models.Count(models.Case(models.When(severity=Defect.SEVERITY_CRITICAL, then=1))),
            major=models.Count(models.Case(models.When(severity=Defect.SEVERITY_MAJOR, then=1))),
            minor=models.Count(models.Case(models.When(severity=Defect.SEVERITY_MINOR, then=1))),
            trivial=models.Count(models.Case(models.When(severity=Defect.SEVERITY_TRIVIAL, then=1))),
        )
        return severity_summary

    @staticmethod
    def is_flaky(status_list):
        if not isinstance(status_list, list):
            status_list = list(status_list)

        # __count = status_list.count()
        __pass_count = status_list.count(TestRunResult.STATUS_PASS)
        __fail_count = status_list.count(TestRunResult.STATUS_FAIL) + status_list.count(TestRunResult.STATUS_BROKEN)

        if __fail_count > 0 and __pass_count > 0:
            return True
        else:
            return False

    def add_caused_by_commits(self, commit, test_suite, cur_recursion_level=1, max_recursion_depth=50):
        if cur_recursion_level > max_recursion_depth:
            err_msg = 'Argument "cur_recursion_level"=%d should ' \
                      'be less than "max_recursion_depth"=%d.' % (cur_recursion_level, max_recursion_depth)
            raise ValueError(err_msg)

        self.caused_by_commits.add(commit)
        # self.caused_by_commits.get_or_create(commit=commit, defect=self)

        for parent_commit in commit.parents.iterator():
            test_runs_old = TestRun.objects.filter(commit=parent_commit, project=self.project, test_suite=test_suite)
            test_run_results = TestRunResult.objects.filter(test_run__in=test_runs_old)
            tests = Test.objects.filter(test_run_results__in=test_run_results)
            add_commit = True
            for test in tests:                
                if test in self.associated_tests.iterator():
                    test_runs_pass = TestRunResult.objects.filter(
                        test=test, commit=parent_commit, test_run__in=test_runs_old, status=TestRunResult.STATUS_PASS)
                    if test_runs_pass.exists():
                        add_commit = False
                        break
            if add_commit and cur_recursion_level < max_recursion_depth:
                self.add_caused_by_commits(parent_commit, test_suite, cur_recursion_level+1)

    def add_closed_by_commits(self, commit, test_suite, cur_recursion_level=1, max_recursion_depth=50):
        if cur_recursion_level > max_recursion_depth:
            err_msg = 'Argument "cur_recursion_level"=%d should ' \
                      'be less than "max_recursion_depth"=%d.' % (cur_recursion_level, max_recursion_depth)
            raise ValueError(err_msg)

        self.closed_by_commits.add(commit)
        for parent_commit in commit.parents.iterator():
            test_runs_old = TestRun.objects.filter(commit=parent_commit, project=self.project, test_suite=test_suite)
            test_run_results = TestRunResult.objects.filter(test_run__in=test_runs_old)
            tests = Test.objects.filter(test_run_results__in=test_run_results)
            add_commit = True
            for test in tests:
                if test in self.associated_tests.iterator():
                    test_runs_fail = TestRunResult.objects.filter(
                        test=test, commit=parent_commit, test_run__in=test_runs_old, status=TestRunResult.STATUS_FAIL)
                    if test_runs_fail.exists():
                        add_commit = False
                        break
            if add_commit and cur_recursion_level < max_recursion_depth:
                self.add_closed_by_commits(parent_commit, test_suite, cur_recursion_level+1)

    @classmethod
    def perform(cls, test_run_result, **kwargs):
        """
        In this function we manage creating, closing and reopening defects basing on 'test_result' argument

        :param test_run_result:
        :param kwargs:
        :return:
        """
        # print 'TEST RUN RESULT: {0}\t{1}\t{2}'.format(test_run_result.id, test_run_result.test, test_run_result.status)
        # print 'KWARGS: {0}'.format(kwargs)

        test = test_run_result.test
        # print 'TEST: {0}'.format(test.name)

        test_run = test_run_result.test_run
        # print 'TEST RUN: {0}'.format(test_run.name)

        test_suite = test_run_result.test_suite
        # print 'TEST SUITE: {0}'.format(test_suite.name)

        project = test_run_result.project
        commit = test_run_result.commit

        auto_raise = test_suite.auto_raise_defect
        # print 'TEST SUITE AUTO RAISE: {0}'.format(auto_raise)
        auto_close = test_suite.auto_close_defect
        # print 'TEST SUITE AUTO CLOSE: {0}'.format(auto_close)

        defect_queryset = cls.objects.filter(project=test_run.project, reason=test_run_result.failure_message)

        if test_run_result.status in [TestRunResult.STATUS_FAIL, TestRunResult.STATUS_BROKEN]:
            if not defect_queryset.exists():
                # TODO: CREATE DEFECT IF AUTO RAISE
                if auto_raise:
                    # defect = cls.objects.create(project=project, reason=test_run_result.failure_message)
                    defect = cls.objects.create(project=project, error=test_run_result.stacktrace)

                    defect.matching = 'unknown'

                    defect.associated_tests.add(test)

                    if test_run_result.failure_message:
                        defect.name = test_run_result.failure_message[:255]
                        defect.reason = test_run_result.failure_message[:255]
                    else:
                        defect.name = 'Defect created from result #{id}'.format(id=test_run_result.id)
                        defect.reason = 'Create by failure status.'

                    test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run, commit=commit).order_by('created').values_list('status', flat=True)

                    if test_run.is_local:
                        defect.type = Defect.TYPE_LOCAL
                    elif Defect.is_flaky(test_run_results):
                        defect.type = Defect.TYPE_FLAKY
                    else:
                        defect.type = Defect.TYPE_PROJECT

                    defect.create_type = Defect.CREATE_TYPE_AUTOMATIC

                    defect.status = Defect.STATUS_NEW
                    defect.severity = Defect.SEVERITY_TRIVIAL
                    defect.priority = 1
                    defect.found_date = timezone.now()

                    # TODO: Link to objects in which defects are found
                    defect.found_test_suites.add(test_suite)
                    defect.found_test_runs.add(test_run)
                    defect.found_test_run_results.add(test_run_result)
                    defect.found_tests.add(test)

                    if commit is not None:
                        defect.found_commits.add(commit)

                    # TODO: Link to objects in which defects are caused (who init this defect)
                    defect.caused_by_test_suites.add(test_suite)
                    defect.caused_by_test_runs.add(test_run)
                    defect.caused_by_test_run_results.add(test_run_result)
                    defect.caused_by_tests.add(test)

                    if commit is not None:
                        add_caused_by_commits_task.delay(defect.id, commit.id, test_suite.id)

                    # TODO: Link to objects in which defects are created (who init this defect)
                    defect.created_by_test_suite = test_suite
                    defect.created_by_test_run = test_run
                    defect.created_by_test_run_result = test_run_result
                    defect.created_by_test = test

                    if commit is not None:
                        defect.created_by_commit = commit

                    # Some fields
                    defect.discovery_phase = ''
                    defect.discovery_method = ''
                    defect.origination_phase = ''
                    defect.root_cause = ''
                    defect.resolution_type = ''
                    defect.leakage_reason = ''

                    if test_run.author:
                        defect.owner = test_run.author

                    defect.save()

            elif defect_queryset.exists():
                for defect in defect_queryset:
                    if defect.status == Defect.STATUS_CLOSED and not defect_queryset.filter(original_defect=defect).exists():
                        # TODO: Reopen defect

                        original_defect_id = defect.id

                        defect.id = None
                        defect.original_defect_id = original_defect_id
                        defect.save()

                        defect.associated_tests.add(test)

                        test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run).order_by('created').values_list('status', flat=True)

                        if Defect.is_flaky(test_run_results):
                            defect.type = Defect.TYPE_FLAKY

                        defect.status = Defect.STATUS_NEW

                        defect.reopen_date = timezone.now()
                        # defect.close_date = None

                        # TODO: Link to objects in which defects are caused (who init this defect)
                        defect.caused_by_test_suites.add(test_suite)
                        defect.caused_by_test_runs.add(test_run)
                        defect.caused_by_test_run_results.add(test_run_result)
                        defect.caused_by_tests.add(test)

                        if commit is not None:
                            add_caused_by_commits_task.delay(defect.id, commit.id, test_suite.id)

                        # TODO: Link to objects in which defects are found
                        defect.found_test_suites.add(test_suite)
                        defect.found_test_runs.add(test_run)
                        defect.found_test_run_results.add(test_run_result)
                        defect.found_tests.add(test)
                        if commit is not None:
                            defect.found_commits.add(commit)

                        # TODO: Link to objects in which defects are reopen (who init reopen defect)
                        defect.reopen_test_suites.add(test_suite)
                        defect.reopen_test_runs.add(test_run)
                        defect.reopen_test_run_results.add(test_run_result)
                        defect.reopen_tests.add(test)
                        if commit is not None:
                            defect.reopen_commits.add(commit)

                        if test_run.author:
                            defect.owner = test_run.author

                        defect.save()

                    else:
                        # TODO: Continue defect status OPEN
                        defect.associated_tests.add(test)
                        test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run, commit=commit).order_by('created').values_list('status', flat=True)

                        if Defect.is_flaky(test_run_results):
                            defect.type = Defect.TYPE_FLAKY

                        defect.found_test_suites.add(test_suite)
                        defect.found_test_runs.add(test_run)
                        defect.found_test_run_results.add(test_run_result)
                        defect.found_tests.add(test)

                        if commit is not None:
                            defect.found_commits.add(commit)

                        defect.save()

        elif test_run_result.status == TestRunResult.STATUS_PASS:
            old_defect_queryset = cls.objects.filter(
                associated_tests=test
            ).exclude(
                models.Q(status=Defect.STATUS_CLOSED) | models.Q(type=Defect.TYPE_FLAKY)
            )

            for defect in old_defect_queryset:

                defect.associated_tests.add(test)

                newest_current_test_run_results = TestRunResult.objects.filter(
                    test=models.OuterRef('id')
                ).order_by('-execution_ended')

                qs = defect.associated_tests.all().annotate(
                    current_status=models.Subquery(newest_current_test_run_results.values('status')[:1])
                ).filter(current_status__in=[TestRunResult.STATUS_FAIL, TestRunResult.STATUS_BROKEN])

                has_failures = qs.exists()

                if auto_close and not has_failures: # TODO: and if have not failures
                    if defect.type not in [Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]:
                        # We don't close defect if commit where we have passed test results is earlier that commit
                        # where defect was created.
                        if commit is not None and defect.created_by_commit is not None:
                            if commit.timestamp < defect.created_by_commit.timestamp:
                                continue
                            # We should close defect only if 'commit' is descendant of 'defect.created_bu_commit'
                            if defect.created_by_commit.is_connected_with_commit(commit) is False:
                                continue

                        # TODO: Defect should be close
                        defect.associated_tests.add(test)

                        defect.close_type = Defect.CLOSE_TYPE_FIXED
                        defect.status = Defect.STATUS_CLOSED

                        defect.close_date = timezone.now()

                        # TODO: Link to objects in which defects are found
                        defect.found_test_suites.add(test_suite)
                        defect.found_test_runs.add(test_run)
                        defect.found_test_run_results.add(test_run_result)
                        defect.found_tests.add(test)

                        if commit is not None:
                            defect.found_commits.add(commit)

                        # TODO: Link to objects in which defects are closed (who init closed defect)
                        defect.closed_test_suite = test_suite
                        defect.closed_test_run = test_run
                        defect.closed_test_run_result = test_run_result
                        defect.closed_test = test

                        if commit is not None:
                            defect.closed_commit = commit
                            # defect.closed_by_commits.add(commit)
                            add_closed_by_commits_task.delay(defect.id, commit.id, test_suite.id)
                        defect.save()

                elif has_failures:
                    test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run, commit=commit).order_by('created').values_list('status', flat=True)

                    if Defect.is_flaky(test_run_results):
                        defect.type = Defect.TYPE_FLAKY

                    defect.save()

                else:
                    pass

        else:
            pass

        return True

    #
    # @classmethod
    # def create(cls, project, test_suite, test, test_run, test_run_result, commit=None, *args, **kwargs):
    #     defect = cls.objects.create(project=test_run_result.project, error=test_run_result.stacktrace)
    #
    #     defect.associated_tests.add(test)
    #     if test_run_result.failure_message:
    #         defect.name = test_run_result.failure_message
    #         defect.reason = test_run_result.failure_message
    #     else:
    #         defect.name = 'Defect created from result #{id}'.format(id=test_run_result.id)
    #         defect.reason = 'Create by failure status.'
    #
    #     defect.matching = 'unknown'
    #
    #     test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run,
    #                                                     commit=commit).order_by('created').values_list('status',
    #                                                                                                    flat=True)
    #
    #     def is_flaky(status_list):
    #         if not isinstance(status_list, list):
    #             status_list = list(status_list)
    #
    #         # __count = status_list.count()
    #         __pass_count = status_list.count(TestRunResult.STATUS_PASS)
    #         __fail_count = status_list.count(TestRunResult.STATUS_FAIL)
    #
    #         if __fail_count > 0 and __pass_count > 0:
    #             return True
    #         else:
    #             return False
    #
    #     if test_run.is_local:
    #         defect.type = Defect.TYPE_LOCAL
    #     elif is_flaky(test_run_results):
    #         defect.type = Defect.TYPE_FLAKY
    #     else:
    #         defect.type = Defect.TYPE_PROJECT
    #
    #     defect.create_type = Defect.CREATE_TYPE_AUTOMATIC
    #
    #     defect.status = Defect.STATUS_NEW
    #     defect.severity = Defect.SEVERITY_TRIVIAL
    #     defect.priority = 1
    #     defect.found_date = timezone.now()
    #
    #     # TODO: Link to objects in which defects are found
    #     defect.found_test_suites.add(test_suite)
    #     defect.found_test_runs.add(test_run)
    #     defect.found_test_run_results.add(test_run_result)
    #     defect.found_tests.add(test)
    #     if commit is not None:
    #         defect.found_commits.add(commit)
    #
    #     # TODO: Link to objects in which defects are caused (who init this defect)
    #     defect.caused_by_test_suites.add(test_suite)
    #     defect.caused_by_test_runs.add(test_run)
    #     defect.caused_by_test_run_results.add(test_run_result)
    #     defect.caused_by_tests.add(test)
    #     if commit is not None:
    #         defect.caused_by_commits.add(commit)
    #
    #     # TODO: Link to objects in which defects are created (who init this defect)
    #     defect.created_by_test_suite = test_suite
    #     defect.created_by_test_run = test_run
    #     defect.created_by_test_run_result = test_run_result
    #     defect.created_by_test = test
    #     if commit is not None:
    #         defect.created_by_commit = commit
    #
    #     # Some fields
    #     defect.discovery_phase = ''
    #     defect.discovery_method = ''
    #     defect.origination_phase = ''
    #     defect.root_cause = ''
    #     defect.resolution_type = ''
    #     defect.leakage_reason = ''
    #
    #     if test_run.author:
    #         defect.owner = test_run.author
    #         # defect.watchers.add(test_run.author)
    #
    #     defect.save()
    #     # defect.send_notification_mail(open=True)
    #     return defect
    #
    # def append(self, test_suite, test, test_run, test_run_result, commit=None, *args, **kwargs):
    #     defect = self
    #     defect.associated_tests.add(test)
    #
    #     test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run,
    #                                                     commit=commit).order_by('created').values_list('status',
    #                                                                                                    flat=True)
    #
    #     def is_flaky(status_list):
    #         if not isinstance(status_list, list):
    #             status_list = list(status_list)
    #
    #         # __count = status_list.count()
    #         __pass_count = status_list.count(TestRunResult.STATUS_PASS)
    #         __fail_count = status_list.count(TestRunResult.STATUS_FAIL)
    #
    #         if __fail_count > 0 and __pass_count > 0:
    #             return True
    #         else:
    #             return False
    #
    #     if is_flaky(test_run_results):
    #         defect.type = Defect.TYPE_FLAKY
    #
    #     defect.found_test_suites.add(test_suite)
    #     defect.found_test_runs.add(test_run)
    #     defect.found_test_run_results.add(test_run_result)
    #     defect.found_tests.add(test)
    #     if commit is not None:
    #         defect.found_commits.add(commit)
    #
    #     # defect.watchers.add(test_run.author)
    #     defect.save()
    #     return defect
    #
    # def reopen(self, test_suite, test, test_run, test_run_result, commit=None, *args, **kwargs):
    #     assert isinstance(self, Defect), 'Incorrect instance class.'
    #
    #     defect = self
    #
    #     defect.associated_tests.add(test)
    #
    #     test_run_results = TestRunResult.objects.filter(test_suite=test_suite, test=test, test_run=test_run,
    #                                                     commit=commit).order_by('created').values_list('status',
    #                                                                                                    flat=True)
    #
    #     def is_flaky(status_list):
    #         if not isinstance(status_list, list):
    #             status_list = list(status_list)
    #
    #         # __count = status_list.count()
    #         __pass_count = status_list.count(TestRunResult.STATUS_PASS)
    #         __fail_count = status_list.count(TestRunResult.STATUS_FAIL)
    #
    #         if __fail_count > 0 and __pass_count > 0:
    #             return True
    #         else:
    #             return False
    #
    #     if is_flaky(test_run_results):
    #         defect.type = Defect.TYPE_FLAKY
    #
    #     defect.status = Defect.STATUS_NEW
    #
    #     defect.reopen_date = timezone.now()
    #     # defect.close_date = None
    #
    #     # TODO: Link to objects in which defects are found
    #     defect.found_test_suites.add(test_suite)
    #     defect.found_test_runs.add(test_run)
    #     defect.found_test_run_results.add(test_run_result)
    #     defect.found_tests.add(test)
    #     if commit is not None:
    #         defect.found_commits.add(commit)
    #
    #     # TODO: Link to objects in which defects are reopen (who init reopen defect)
    #     defect.reopen_test_suites.add(test_suite)
    #     defect.reopen_test_runs.add(test_run)
    #     defect.reopen_test_run_results.add(test_run_result)
    #     defect.reopen_tests.add(test)
    #     if commit is not None:
    #         defect.reopen_commits.add(commit)
    #
    #     # TODO: Link to objects in which defects are caused (who init this defect)
    #     defect.caused_by_test_suites.add(test_suite)
    #     defect.caused_by_test_runs.add(test_run)
    #     defect.caused_by_test_run_results.add(test_run_result)
    #     defect.caused_by_tests.add(test)
    #     if commit is not None:
    #         defect.caused_by_commits.add(commit)
    #
    #     # Some fields
    #     # defect.discovery_phase = ''
    #     # defect.discovery_method = ''
    #     # defect.origination_phase = ''
    #     # defect.root_cause = ''
    #     # defect.resolution_type = ''
    #     # defect.leakage_reason = ''
    #     if test_run.author:
    #         defect.owner = test_run.author
    #         # defect.watchers.add(test_run.author)
    #
    #     defect.save()
    #     # defect.send_notification_mail(reopen=True)
    #     return defect
    #
    # def close(self, test_suite, test, test_run, test_run_result, commit=None, *args, **kwargs):
    #     assert isinstance(self, Defect), 'Incorrect instance class.'
    #
    #     defect = self
    #
    #     defect.associated_tests.add(test)
    #
    #     defect.close_type = Defect.CLOSE_TYPE_FIXED
    #     defect.status = Defect.STATUS_CLOSED
    #
    #     defect.close_date = timezone.now()
    #
    #     # TODO: Link to objects in which defects are found
    #     defect.found_test_suites.add(test_suite)
    #     defect.found_test_runs.add(test_run)
    #     defect.found_test_run_results.add(test_run_result)
    #     defect.found_tests.add(test)
    #     if commit is not None:
    #         defect.found_commits.add(commit)
    #
    #     # TODO: Link to objects in which defects are closed (who init closed defect)
    #     defect.closed_test_suite = test_suite
    #     defect.closed_test_run = test_run
    #     defect.closed_test_run_result = test_run_result
    #     defect.closed_test = test
    #     if commit is not None:
    #         defect.closed_commit = commit
    #
    #     # if test_run.author:
    #     # defect.watchers.add(test_run.author)
    #
    #     defect.save()
    #     # defect.send_notification_mail(close=True)
    #     return defect


class DefectAttachment(models.Model):
    defect = models.ForeignKey('Defect', related_name='defect_attachments', blank=False, null=False,
                               on_delete=models.CASCADE)

    name = models.CharField(max_length=255, blank=False, null=False)

    file = models.FileField(upload_to='uploads', blank=True, null=True)

    class Meta(object):
        verbose_name = _(u'defect attachment')
        verbose_name_plural = _(u'defect attachments')

    def __unicode__(self):
        return u'{id} {name}'.format(id=self.id, name=self.name)


class TimeStampedM2M(models.Model):
    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now_add=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        abstract = True


class DefectCausedByCommits(TimeStampedM2M):
    commit = models.ForeignKey(
        "vcs.Commit",
        on_delete=models.CASCADE
    )

    defect = models.ForeignKey(
        "Defect",
        on_delete=models.CASCADE
    )

    class Meta(object):
        db_table = "testing_defect_caused_by_commits"


class DefectClosedByCommits(TimeStampedM2M):
    commit = models.ForeignKey(
        "vcs.Commit",
        on_delete=models.CASCADE
    )

    defect = models.ForeignKey(
        "Defect",
        on_delete=models.CASCADE
    )

    class Meta(object):
        db_table = "testing_defect_closed_by_commits"


class TestAssociatedFiles(TimeStampedM2M):
    file = models.ForeignKey(
        "vcs.File",
        on_delete=models.CASCADE
    )

    test = models.ForeignKey(
        "Test",
        on_delete=models.CASCADE
    )

    class Meta(object):
        db_table = "testing_test_associated_files"


class TestAssociatedAreas(TimeStampedM2M):
    area = models.ForeignKey(
        "vcs.Area",
        on_delete=models.CASCADE
    )

    test = models.ForeignKey(
        "Test",
        on_delete=models.CASCADE
    )

    class Meta(object):
        db_table = "testing_test_associated_areas"
