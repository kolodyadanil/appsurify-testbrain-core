# -*- coding: utf-8 -*-

import os
import time
from shutil import rmtree
from datetime import datetime
from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

from github import Github

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import ugettext_lazy as _
import re
import uuid
import tempfile


User = get_user_model()

ref_pattern = re.compile(r"(^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)|/head(s)?|\d+/head(s)?|/merge(s)?|\d+/merge(s)?|\.lock)")



class GithubRepository(models.Model):
    project = models.OneToOneField('project.Project', related_name='github_repository', null=False,
                                   on_delete=models.CASCADE)
    github_repository_name = models.CharField(max_length=255, blank=False, null=False)
    user = models.ForeignKey(User, related_name='github_repository', null=False, on_delete=models.CASCADE)
    token = models.CharField(max_length=50, blank=False, null=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Github repository')
        verbose_name_plural = _('Github repositories')

    def __str__(self):
        return self.github_repository_name

    def delete(self, using=None, keep_parents=False):
        if os.path.exists(self.repo_path):
            rmtree(self.repo_path, ignore_errors=True)
        return super(GithubRepository, self).delete(using, keep_parents)

    def get_repo_path(self, ref=None, before=None, after=None):
        tmp_dir = os.path.join(tempfile.gettempdir(), 'repositories')
        # tmp_dir = os.path.join(
        #     settings.STORAGE_ROOT,
        #     'organizations',
        #     str(self.project.organization_id),
        #     'repositories',
        #     str(self.project.id)
        # )
        bit_dir = "{url}:{ref}:{before}:{after}".format(
            url=self.url_repository_with_token(),
            ref=ref,
            before=before,
            after=after
        )
        uuid_dir = str(uuid.uuid5(namespace=uuid.NAMESPACE_URL, name=bit_dir))
        dir = os.path.join(tmp_dir, uuid_dir)
        return dir

    def get_repo(self, ref=None, before=None, after=None, force=False):
        repo_path = self.get_repo_path(ref=ref, before=before, after=after)

        if force:
            rmtree(repo_path, ignore_errors=True)
        try:
            repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            repo = None
            rmtree(repo_path, ignore_errors=True)
        except NoSuchPathError:
            repo = None
            rmtree(repo_path, ignore_errors=True)
        except Exception:
            repo = None
            rmtree(repo_path, ignore_errors=True)

        _tries = 0
        while not repo:
            _tries += 1
            try:
                repo = Repo.clone_from(
                    url=self.url_repository_with_token(),
                    to_path=repo_path,
                    branch=ref,
                    mirror=True
                )
                break
            except GitCommandError as exc:
                rmtree(repo_path, ignore_errors=True)
                time.sleep(5)
                if exc.stderr.find("not found") != -1:
                    ref = ""
            except Exception as exc:
                rmtree(repo_path, ignore_errors=True)
                time.sleep(5)
                if _tries >= 3:
                    raise exc

        return repo

    @staticmethod
    def get_full_list_repos(token_obj):
        access_token = token_obj.token
        g = Github(access_token)
        repos = [{
            'full_name': repo.full_name,
            'link': repo.html_url,
            'is_admin': repo.permissions.admin
        } for repo in g.get_user().get_repos()]
        return repos

    def get_or_refresh_token(self):
        return ''

    def url_repository_with_token(self):
        return 'https://{}@github.com/{}'.format(self.token, self.github_repository_name)

    def url_commit(self, sha):
        return 'https://github.com/{}/commits/{}'.format(self.github_repository_name, sha)

    def get_refs(self, ref=None, before=None, after=None):
        # refs = list([ref for ref in self.repo.remote('origin').refs])
        # if refspec:
        #     refspec = re.sub(ref_pattern, "", refspec)
        #     refs = filter(lambda ref: refspec in ref.remote_head, [ref for ref in refs])
        # refs.sort(key=lambda ref: ref.commit.committed_datetime, reverse=True)
        # repo = self.repo
        # refs = list(set(filter(lambda x: x != "", [re.sub(ref_pattern, "", ref.name) for ref in repo.refs])))
        repo = self.get_repo(ref=ref, before=before, after=after)
        if repo is None:
            raise Exception("Clone git repository first.")

        refs = list([branch.name for branch in repo.branches])
        return refs

    def get_commits(self, ref=None, before=None, after=None, refspec=None):
        repo = self.get_repo(ref=ref, before=before, after=after)
        if repo is None:
            raise Exception("Clone git repository first.")

        rev = refspec
        if before and after:
            rev = '{}..{}'.format(before, after)
        elif before is None and after:
            rev = after

        commits = repo.iter_commits(rev=rev, reverse=True)
        commits = list([commit for commit in commits])
        return commits

    def get_webhook_event_by_name(self, name):
        from .events import event_create, event_push, event_issue, event_delete
        events = {
            'push': event_push,
            'create': event_create,
            # 'delete': event_delete,
            'issues': event_issue,
        }
        event_func = events.get(name)
        return event_func

    def handling_push_webhook_payload(self, data=None):

        if data is None:
            data = {}

        ref = data.get('ref', "")
        ref = re.sub(ref_pattern, "", ref)

        before = data.get('before')
        if before == '0' * 40:
            before = None

        after = data.get('after')
        if after == '0' * 40:
            after = None

        return {'ref': ref, 'before': before, 'after': after}

    def receive_webhook(self, request, context, *args, **kwargs):
        status, message = True, ''

        event = request.META.get('HTTP_X_GITHUB_EVENT')

        if event == 'ping':
            status, message = True, 'OK'
            return status, message

        event_func = self.get_webhook_event_by_name(event)
        if event_func is None:
            status, message = False, 'Unsupported webhook event.'

        try:
            message = event_func(request.data, self.id)
        except Exception as exc:
            status, message = False, repr(exc)

        return status, message

    @staticmethod
    def processing_commits_fast(project, repository, data):
        from applications.integration.github.utils import processing_commits_fast
        result = processing_commits_fast(project=project, repository=repository, data=data)
        return result


class GithubHook(models.Model):
    project = models.OneToOneField('project.Project', related_name='web_hook', null=False, on_delete=models.CASCADE)
    id_hook = models.IntegerField(blank=False, null=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Github hook')
        verbose_name_plural = _('Github hooks')


class GithubIssue(models.Model):
    defect = models.ForeignKey('testing.Defect', related_name='issue', null=False, on_delete=models.CASCADE)
    issue_number = models.IntegerField(blank=False, null=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        verbose_name = _('Github issue')
        verbose_name_plural = _('Github issues')
