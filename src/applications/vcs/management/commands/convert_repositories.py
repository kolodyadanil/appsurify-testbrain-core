import os
import shutil

from django.conf import settings
from django.core.management import BaseCommand

from applications.project.models import Project


class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.all()
        for project in projects:
            local_path = '{}/organizations/{}/projects/{}'.format(settings.STORAGE_ROOT,
                                                                  project.organization_id, project.id)
            try:
                if hasattr(project, 'github_repository'):
                    project.github_repository.pull_repository()
                    if os.path.exists(local_path):
                        shutil.rmtree(local_path, ignore_errors=True)
                    project.github_repository.clone_repository()
                elif hasattr(project, 'git_repository'):
                    project.git_repository.pull_repository()
                    if os.path.exists(local_path):
                        shutil.rmtree(local_path, ignore_errors=True)
                    project.git_repository.clone_repository()
                elif hasattr(project, 'bitbucket_repository'):
                    project.bitbucket_repository.pull_repository()
                    if os.path.exists(local_path):
                        shutil.rmtree(local_path, ignore_errors=True)
                    project.bitbucket_repository.clone_repository()
                elif hasattr(project, 'git_ssh_repository'):
                    project.git_ssh_repository.pull_repository()
                    if os.path.exists(local_path):
                        shutil.rmtree(local_path, ignore_errors=True)
                    project.git_ssh_repository.clone_repository()
            except Exception as e:
                print('Error in {} project'.format(project.id))
                print(e)
                continue
