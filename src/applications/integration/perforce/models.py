# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import re
import shutil
import subprocess
import pexpect
from time import sleep
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import ugettext_lazy as _
from git import *


User = get_user_model()
ref_pattern = re.compile(
    r"(^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)|/head(s)?|\d+/head(s)?|/merge(s)?|\d+/merge(s)?|\.lock)")


class PerforceRepository(models.Model):
    project = models.OneToOneField('project.Project', related_name='perforce_repository', null=False,
                                   on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='perforce_repository', null=False,
                             on_delete=models.CASCADE)

    host = models.CharField(max_length=255, blank=False, null=False)
    port = models.CharField(max_length=6, blank=True, null=False, default=str(1666))
    username = models.CharField(max_length=255, blank=False, null=False)
    password = models.CharField(max_length=255, blank=False, null=False)
    client = models.CharField(max_length=255, blank=False, null=False)

    depot = models.CharField(max_length=255, blank=False, null=False)
    detect_branches = models.BooleanField(default=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Perforce repository')
        verbose_name_plural = _('Perforce repositories')

    def __str__(self):
        return str(self.id)

    @property
    def repo_path(self):
        return os.path.join(settings.STORAGE_ROOT, 'organizations',
                            str(self.project.organization_id), 'projects', str(self.project_id))

    def delete(self, using=None, keep_parents=False):
        local_path = '{}/organizations/{}/projects/{}'.format(
            settings.STORAGE_ROOT,
            self.project.organization_id,
            self.project_id
        )

        if os.path.exists(local_path):
            shutil.rmtree(local_path, ignore_errors=True)

        return super(PerforceRepository, self).delete(using, keep_parents)

    def url_commit(self, sha):
        return ''

    @property
    def local_path(self):
        local_path = '{}/organizations/{}/projects/{}'.format(
            settings.STORAGE_ROOT,
            self.project.organization_id,
            self.project_id
        )
        return local_path

    def p4_login(self):
        try:
            prev_path = os.getcwd()
            os.chdir(self.local_path)
        except OSError:
            return False

        commandLine = 'p4 -u {username} -p {port} -c {client} login'.format(
            username=self.username,
            port="{}:{}".format(self.host, self.port),
            client=self.client
        )

        proc = pexpect.spawn(commandLine)

        out = proc.expect(['Enter password:', pexpect.EOF, pexpect.TIMEOUT])

        if out == 0:
            proc.sendline(self.password)
            sleep(5)
            os.chdir(prev_path)
            return True
        else:
            return False

    def clone_repository(self, force=False):

        local_path = self.repo_path

        git_path = os.path.join(local_path, '.git')
        if force:
            shutil.rmtree(local_path, ignore_errors=True)

        if not os.path.exists(local_path):
            os.makedirs(local_path)

        result = self.p4_login()
        if not result:
            raise Exception('Authentication Failure.')

        repo = Repo.init(local_path, mkdir=True)
        repo.config_writer().set_value("git-p4", "user", self.username).release()
        repo.config_writer().set_value("git-p4", "password", self.password).release()
        repo.config_writer().set_value("git-p4", "client", self.client).release()
        repo.config_writer().set_value("git-p4", "host", self.host).release()
        repo.config_writer().set_value("git-p4", "port", "{}:{}".format(self.host, self.port)).release()
        repo.config_writer().set_value("git-p4", "retries", "3").release()

        commandLine = 'cd {dir}; git p4 clone {detect}{depot} .'.format(
            detect='--detect-branches ' if self.detect_branches else '',
            depot=self.depot,
            dir=local_path
        )
        process = subprocess.Popen(
            commandLine,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out = process.stdout.read().strip()
        out = out.decode("utf-8", errors="ignore")
        # print out
        error = process.stderr.read().strip()
        error = error.decode("utf-8", errors="ignore")
        # print error

        if error:
            return False
        return True

    def pull_repository(self):
        local_path = self.repo_path

        commandLine = 'cd {dir}; git p4 sync'.format(
            dir=local_path
        )

        process = subprocess.Popen(
            commandLine,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out = process.stdout.read().strip()
        out = out.decode("utf-8", errors="ignore")
        # print out
        error = process.stderr.read().strip()
        error = error.decode("utf-8", errors="ignore")
        # print error
        if error:
            return False
        return True

    def receive_webhook(self, request, context, *args, **kwargs):
        from .events import event_push
        status, message = True, ''
        try:
            message = event_push(self.id)
        except Exception as exc:
            status, message = False, repr(exc)
        return status, message

    @staticmethod
    def processing_commits_fast(project, repository, data):
        return True
