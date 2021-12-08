# -*- coding: utf-8 -*-

import os
import re
from shutil import rmtree
from datetime import datetime
from git import Repo, InvalidGitRepositoryError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.utils.translation import ugettext_lazy as _

from .utils import test_connection, install_hook, generate_hook, perform_execution


User = get_user_model()

ref_pattern = re.compile(
    r"(^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)|/head(s)?|\d+/head(s)?|/merge(s)?|\d+/merge(s)?|\.lock)")


class GitRepository(models.Model):
    project = models.OneToOneField('project.Project', related_name='git_repository', null=False,
                                   on_delete=models.DO_NOTHING)
    git_repository_name = models.CharField(max_length=255, blank=False, null=False)
    user = models.ForeignKey(User, related_name='local_repository', null=False, on_delete=models.DO_NOTHING)
    host = models.CharField(max_length=255, blank=False, null=False)
    port = models.CharField(max_length=6, blank=True, null=False, default=str(22))
    login = models.CharField(max_length=255, blank=False, null=False)
    password = models.CharField(max_length=255, blank=True, null=False)
    path = models.TextField(blank=True, null=False)
    is_installed_hook = models.BooleanField(default=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Git repository')
        verbose_name_plural = _('Git repositories')

    def __str__(self):
        return self.git_repository_name

    def delete(self, using=None, keep_parents=False):
        if os.path.exists(self.repo_path):
            rmtree(self.repo_path, ignore_errors=True)
        return super(GitRepository, self).delete(using, keep_parents)

    @property
    def repo_path(self):
        return os.path.join(settings.STORAGE_ROOT, 'organizations', str(self.project.organization_id),
                            'projects', str(self.project_id))

    @property
    def repo(self):
        try:
            repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            repo = None
        return repo

    @staticmethod
    def test_connection(host, port, user, password):
        status_connection, message = test_connection(host=host, user=user, password=password, port=port)
        return status_connection, message

    @staticmethod
    def get_full_list_repos(token_obj):
        return []

    def get_or_refresh_token(self):
        return ''

    def url_repository_with_token(self):
        if self.path[0] == '/':
            return 'ssh://{}@{}:{}{}'.format(self.login, self.host, self.port, self.path)
        elif self.path[0] == '~':
            return 'ssh://{}@{}:{}/{}'.format(self.login, self.host, self.port, self.path)
        else:
            return 'ssh://{}@{}:{}/~/{}'.format(self.login, self.host, self.port, self.path)

    def url_commit(self, sha):
        return ''

    def install_webhook(self, request, context, *args, **kwargs):
        username, repos_name = self.git_repository_name.split('/')
        scheme = request.scheme
        domain = '{}://{}'.format(scheme, get_current_site(request))
        hook = generate_hook(domain=domain, username=username, repos_name=repos_name, project_id=self.project_id)
        status, message = install_hook(host=self.host, login=self.login, password=self.password,
                                       port=self.port, path=self.path, hook=hook, force=True)
        return status, message

    def generate_webhook(self, request, context, *args, **kwargs):
        username, repos_name = self.git_repository_name.split('/')
        scheme = request.scheme
        domain = '{}://{}'.format(scheme, get_current_site(request))
        hook = generate_hook(domain=domain, username=username, repos_name=repos_name, project_id=self.project_id)
        return hook

    def clone_repository(self, force=False):

        if force:
            rmtree(self.repo_path, ignore_errors=True)

        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)

        command = 'git clone --mirror {} {}'.format(self.url_repository_with_token(), self.repo_path)
        result = perform_execution(self, command)

        repo = self.repo

        if not repo.config_reader('repository').has_option('remote "origin"', 'fetch'):
            repo.config_writer().add_value('remote "origin"', 'fetch', '+refs/heads/*:refs/remotes/origin/*').release()
        else:
            repo.config_writer().set_value('remote "origin"', 'fetch', '+refs/heads/*:refs/remotes/origin/*').release()

        return True

    def fetch_repository(self, refspec=None):

        repo = self.repo

        if repo is None:
            self.clone_repository(force=True)

        if refspec:
            refspec = re.sub(ref_pattern, "", refspec)

        command = 'git fetch --all'
        result = perform_execution(self, command)
        refs = self.get_refs()

        return refs

    def get_refs(self, refspec=None):
        # refs = list([ref for ref in self.repo.remote('origin').refs])
        # if refspec:
        #     refspec = re.sub(ref_pattern, "", refspec)
        #     refs = filter(lambda ref: refspec in ref.remote_head, [ref for ref in refs])
        # refs.sort(key=lambda ref: ref.commit.committed_datetime, reverse=True)
        repo = self.repo
        refs = list(set(filter(lambda x: x != "", [re.sub(ref_pattern, "", ref.name) for ref in repo.refs])))
        return refs

    def get_commits(self, refspec=None, before=None, after=None):
        if refspec is not None:
            refspec = re.sub(ref_pattern, "", refspec)
        if before and after:
            refspec = '{}..{}'.format(before, after)
        elif before is None and after:
            refspec = after
        repo = self.repo
        commits = repo.iter_commits(rev=refspec, reverse=True)
        commits = list([commit for commit in commits])
        return commits

    def get_webhook_event_by_name(self, name):
        from .events import event_commit, event_tag, event_delete
        events = {
            'push': event_commit,
            'create': event_tag,
            # 'delete': event_delete,
        }
        event_func = events.get(name)
        return event_func

    def handling_push_webhook_payload(self, data=None):

        if data is None:
            data = {}

        ref = data.get('ref', "")
        ref = re.sub(ref_pattern, "", ref)

        before = data['before']
        if before == '0' * 40:
            before = None

        after = data['after']
        if after == '0' * 40:
            after = None

        return {'ref': ref, 'before': before, 'after': after}

    def receive_webhook(self, request, context, *args, **kwargs):

        status, message = True, ''

        event = request.META.get('HTTP_X_GIT_EVENT')

        event_func = self.get_webhook_event_by_name(event)

        if event_func is None:
            status, message = False, 'Unsupported webhook event.'

        try:
            message = event_func(request.data, self.id)
        except Exception as exc:
            status, message = False, exc.message

        return status, message

