from django.core.management import BaseCommand

from applications.project.models import Project
from applications.testing.utils.prediction.output.additional_model import additional_output_model_analyzer
from applications.testing.utils.prediction.output.initial_model import initial_output_model_analyzer


class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.all()
        for project in projects:

            if project.defects.count() >= 20:
                result = additional_output_model_analyzer(project_id=project.id, commits_hashes=None)
            else:
                result = initial_output_model_analyzer(project_id=project.id, commits_hashes=None)
            # print result
            # print project.id
