# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import *


class TestReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'test_suite', 'name', 'format', 'status', 'created', 'updated')
    list_filter = ['project', ]


class TestTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created', 'updated')


class StepAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created', 'updated')


class TestStepAdmin(admin.ModelAdmin):
    list_display = ('id', 'step', 'test', 'created', 'updated')


class TestStepTabularInline(admin.TabularInline):
    model = TestStep


class TestAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'name', 'area', 'created', 'updated')
    list_filter = ('project', )
    inlines = (TestStepTabularInline,)
    raw_id_fields = ('project', 'area', 'associated_files', 'associated_areas')


class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created', 'updated')
    list_filter = ('project', )
    raw_id_fields = ('project', 'tests', )


class TestRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'name', 'status', 'created', 'updated')
    raw_id_fields = ('project', 'author', 'areas', 'test_suite', 'tests', 'commit', 'previous_test_run')
    list_filter = ('project', )


class TestRunResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'project_name', 'test_suite_name',
                    'test_run_name', 'area_name', 'test_name',
                    'step_name', 'status', 'created', 'updated')
    raw_id_fields = ('commit', 'test_run', 'test',)
    list_filter = ('project', )


class DefectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project', 'owner', 'type',
                    'status', 'created_by_commit_field', 'closed_by_commit_field',
                    'caused_by_commits_field', )
    list_filter = ('project', )
    raw_id_fields = (
        'project',
        'owner',
        'associated_tests',
        'found_test_suites',
        'found_test_runs',
        'found_test_run_results',
        'found_tests',
        'found_commits',
        'caused_by_test_suites',
        'caused_by_test_runs',
        'caused_by_test_run_results',
        'caused_by_tests',
        'caused_by_commits',
        'reopen_test_suites',
        'reopen_test_runs',
        'reopen_test_run_results',
        'reopen_tests',
        'reopen_commits',
        'original_defect',
        'created_by_test_suite',
        'created_by_test_run',
        'created_by_test_run_result',
        'created_by_test',
        'created_by_commit',
        'closed_test_suite',
        'closed_test_run',
        'closed_test_run_result',
        'closed_test',
        'closed_commit',
        'closed_by_commits'
    )

    # filter_horizontal = ('associated_tests', )

    def closed_by_commit_field(self, obj):
        try:
            return obj.closed_commit.display_id
        except AttributeError:
            return None

    closed_by_commit_field.empty_value_display = '(None)'
    closed_by_commit_field.short_description = 'Closed by commits'
    closed_by_commit_field.admin_order_field = 'closed_commit_id'

    def created_by_commit_field(self, obj):
        try:
            return obj.created_by_commit.display_id
        except AttributeError:
            return None

    created_by_commit_field.empty_value_display = '(None)'
    created_by_commit_field.short_description = 'Created by commits'
    created_by_commit_field.admin_order_field = 'created_by_commit_id'

    def caused_by_commits_field(self, obj):
        if obj.caused_by_commits.exists():
            return ', '.join([x.display_id for x in obj.caused_by_commits.all()])
        else:
            return None

    caused_by_commits_field.empty_value_display = '(None)'
    caused_by_commits_field.short_description = 'Caused by commits'
    caused_by_commits_field.admin_order_field = 'caused_by_commits__id'


admin.site.register(TestReport, TestReportAdmin)
admin.site.register(TestType, TestTypeAdmin)
admin.site.register(Test, TestAdmin)
admin.site.register(Step, StepAdmin)
admin.site.register(TestStep, TestStepAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
admin.site.register(TestRun, TestRunAdmin)
admin.site.register(TestRunResult, TestRunResultAdmin)
admin.site.register(Defect, DefectAdmin)

