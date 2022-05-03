from time import sleep

import os
import pexpect
from django.conf import settings
from django.core.management import BaseCommand
from git import Repo

from applications.project.models import Project


class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.all()
        for project in projects:
            path = '{}/organizations/{}/projects/{}/'.format(settings.STORAGE_ROOT, project.organization.id, project.id)

            if os.path.exists(path):
                continue
            github_integration = self._get_github_integration(project)
            if github_integration:
                url_clone = 'https://{}@github.com/{}'.format(github_integration.token,
                                                              github_integration.github_repository_name)
                Repo.clone_from(url_clone, path)

            git_integration = self._get_local_integration(project)
            if git_integration:
                username = git_integration.login
                password = git_integration.password
                host = git_integration.host
                port = git_integration.port
                remote_path = git_integration.path
                url = 'ssh://{}@{}:{}/~/{}'.format(username, host, port, remote_path)
                proc = pexpect.spawn('git clone {} {}'.format(url, path))
                out = proc.expect(['yes', 'password', pexpect.EOF, pexpect.TIMEOUT])
                if out == 0:
                    proc.sendline('yes')
                    proc.expect(['password'])
                    proc.sendline(password)
                    sleep(5)
                elif out == 1:
                    proc.sendline(password)
                    sleep(5)

    def _get_github_integration(self, project):
        try:
            return project.github_repository
        except:
            return None

    def _get_local_integration(self, project):
        try:
            return project.git_repository
        except:
            return None
