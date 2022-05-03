import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from applications.project.models import Project
from applications.testing.utils.prediction.riskiness.fast_model import fast_model_analyzer
from applications.testing.utils.prediction.riskiness.slow_model import slow_model_analyzer


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
                "You can run `manage.py analyze_riskiness_commits` in your project "
                "to create one manually."
            )

    return wrapper


class NotRunningInTTYException(Exception):
    pass


class Command(BaseCommand):
    help = 'Used to analyze riskiness commits in all projects.'
    requires_migrations_checks = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.storage_path = settings.STORAGE_ROOT

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        project_id = options.get('project_id')

        if project_id:
            projects = Project.objects.filter(id=project_id).only('id')
        else:
            projects = Project.objects.all().only('id')

        for project in projects:
            result = fast_model_analyzer(project_id=project.id)

            if result:
                print('{project_name} fast analyzed'.format(project_name=project.name))
            else:
                print('{project_name} fast not analyzed'.format(project_name=project.name))

        for project in projects:
            result = slow_model_analyzer(project_id=project.id)

            if result:
                print('{project_name} slow analyzed'.format(project_name=project.name))
            else:
                print('{project_name} slow not analyzed'.format(project_name=project.name))

    def add_arguments(self, parser):
        parser.add_argument(
            '--task', dest='task',
            default=False,
            help='Run as task',
            type=bool
        )
        parser.add_argument(
            '--project_id', dest='project_id',
            default=False,
            help='Project id',
            type=int
        )
