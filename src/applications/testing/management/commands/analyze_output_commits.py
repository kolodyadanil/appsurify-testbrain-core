import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from applications.project.models import Project
from applications.testing.utils.prediction.output.additional_model import additional_output_model_analyzer
from applications.testing.utils.prediction.output.initial_model import initial_output_model_analyzer
# from djangotasks import task


def error_handler(f):
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.stderr.write("\nOperation cancelled.")
            sys.exit(1)

        except NotRunningInTTYException:
            self.stdout.write(
                "Analyze commits skipped due to not running in a TTY. "
                "You can run `manage.py analyze_output_commits` in your project "
                "to create one manually."
            )

    return wrapper


class NotRunningInTTYException(Exception):
    pass


class Command(BaseCommand):
    help = 'Used to analyze output commits in all projects.'
    requires_migrations_checks = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.storage_path = settings.STORAGE_ROOT

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        if options.get('task') is True:
            # create_models_task().run()
            pass
        else:
            analyze()

    def add_arguments(self, parser):
        parser.add_argument(
            '--task', dest='task',
            default=False,
            help='Run as task',
            type=bool
        )


def analyze():
    projects = Project.objects.all()

    for project in projects:
        if project.defects.count() >= 20:
            result = additional_output_model_analyzer(project_id=project.id)
        else:
            result = initial_output_model_analyzer(project_id=project.id)

        if result:
            print('{project_name} outputs analyzed'.format(project_name=project.name))
        else:
            print('{project_name} outputs not analyzed'.format(project_name=project.name))


# @task
def create_models_task():
    analyze()
