import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from applications.project.models import Project
from applications.testing.utils.prediction.output.initial_model import create_initial_output_model
from applications.vcs.models import Commit


def error_handler(f):
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.stderr.write("\nOperation cancelled.")
            sys.exit(1)

        except NotRunningInTTYException:
            self.stdout.write("Create a projects repositories models for calculating output commits skipped due to not running in a TTY. You can run `manage.py create_output_models` in your project to create one manually.")

    return wrapper


class NotRunningInTTYException(Exception):
    pass


class Command(BaseCommand):
    help = 'Used to create a projects repositories models for calculating initial output commits.'
    requires_migrations_checks = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ProjectModel = Project
        self.CommitsModel = Commit
        self.storage_path = settings.STORAGE_ROOT

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        project_id = options.get('project_id')

        if not project_id:
            return False

        projects = self.ProjectModel.objects.filter(id=project_id)

        for project in projects:
            if project.defects.count() < 20:
                continue

            initial_output_model = create_initial_output_model(project_id=project.id)

            if initial_output_model:
                print('{project_name} initial output model created'.format(project_name=project.name))
            else:
                print('{project_name} initial output model not created'.format(project_name=project.name))

    def add_arguments(self, parser):
        parser.add_argument(
            '--project_id', dest='project_id',
            default=False,
            help='Project id for default model',
            type=int
        )
