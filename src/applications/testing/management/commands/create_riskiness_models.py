# -*- coding: utf-8 -*-
import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from applications.project.models import Project
from applications.testing.utils.prediction.riskiness.fast_model import create_fast_model
from applications.testing.utils.prediction.riskiness.slow_model import create_slow_model, update_slow_commits_metrics
# from djangotasks import task


def create_models():
    projects = Project.objects.all().only('id')

    for project in list(projects):
        fast_model_result = create_fast_model(project_id=project.id)

        if fast_model_result:
            print('{project_name} fast model created'.format(project_name=project.name))
        else:
            print('{project_name} fast model not created'.format(project_name=project.name))

    for project in projects:
        update_slow_commits_metrics(project_id=project.id)
        slow_model_result = create_slow_model(project_id=project.id)

        if slow_model_result:
            print('{project_name} slow model created'.format(project_name=project.name))
        else:
            print('{project_name} slow model not created'.format(project_name=project.name))

    return True


# @task
# def create_models_task():
#     create_models()
#
#
# def error_handler(f):
#     def wrapper(self, *args, **kwargs):
#         try:
#             return f(self, *args, **kwargs)
#         except KeyboardInterrupt:
#             self.stderr.write("\nOperation cancelled.")
#             sys.exit(1)
#
#         except NotRunningInTTYException:
#             self.stdout.write(
#                 "Create a projects repositories models for predicting bug commits skipped due to not running in a TTY. "
#                 "You can run `manage.py create_riskiness_models` in your project "
#                 "to create one manually."
#             )
#
#     return wrapper
#
#
# class NotRunningInTTYException(Exception):
#     pass


class Command(BaseCommand):
    help = 'Used to create a projects repositories models for predicting bug commits.'
    requires_migrations_checks = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.storage_path = settings.STORAGE_ROOT

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    def handle(self, *args, **options):
        if options.get('task') is True:
            # create_models_task().run()
            pass
        else:
            create_models()

    def add_arguments(self, parser):
        parser.add_argument(
            '--task', dest='task',
            default=False,
            help='Run as task',
            type=bool
        )

