from django.core.management import BaseCommand

from applications.project.models import Project
from applications.vcs.models import Area


class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.all()
        for project in projects:
            try:
                Area.create_from_folders(project.id)
            except Exception as e:
                print('Error in {} project'.format(project.id))
                print(e)
                continue
            