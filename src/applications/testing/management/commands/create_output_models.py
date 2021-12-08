import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from applications.project.models import Project
from applications.testing.utils.prediction.output.additional_model import create_additional_output_model
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
                "Create a projects repositories models for calculating output commits skipped due to not running in a TTY. "
                "You can run `manage.py create_output_models` in your project "
                "to create one manually."
            )

    return wrapper


class NotRunningInTTYException(Exception):
    pass


class Command(BaseCommand):
    help = 'Used to create a projects repositories models for calculating initial output commits.'
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
            create_models()

    def add_arguments(self, parser):
        parser.add_argument(
            '--task', dest='task',
            default=False,
            help='Run as task',
            type=bool
        )


def create_models():
    projects = Project.objects.all().only('id')

    for project in projects:
        if project.defects.count() < 20:
            continue

        additional_output_model = create_additional_output_model(project_id=project.id)

        if additional_output_model:
            print('{project_name} additional output model created'.format(project_name=project.name))
        else:
            print('{project_name} additional output model not created'.format(project_name=project.name))


# @task
def create_models_task():
    create_models()
