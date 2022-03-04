# -*- coding: utf-8 -*-

import base64
import re
import uuid
import tempfile
from shutil import rmtree
import os
from os import chmod
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import ugettext_lazy as _
from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError


User = get_user_model()
ref_pattern = re.compile(
    r"(^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)|/head(s)?|\d+/head(s)?|/merge(s)?|\d+/merge(s)?|\.lock)")


class GitSSHRepository(models.Model):
    project = models.OneToOneField('project.Project', related_name='git_ssh_repository', null=False, on_delete=models.CASCADE)
    repository_name = models.CharField(max_length=255, blank=False, null=False)
    url_repository = models.CharField(max_length=512, blank=False, null=False)
    private_key = models.TextField(blank=False, null=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Git SSH repository')
        verbose_name_plural = _('Git SSH repositories')

    def save(self, *args, **kwargs):
        init = not self.pk
        if init:
            regex = re.compile(r"^.*?:(?P<repo_name>.*)")
            matches = regex.match(self.url_repository).groupdict()
            self.repository_name = matches.get('repo_name')

        super(GitSSHRepository, self).save(*args, **kwargs)

    def __str__(self):
        return self.repository_name

    def delete(self, using=None, keep_parents=False):
        from shutil import rmtree
        from os import path
        local_path = '{}/organizations/{}/projects/{}'.format(settings.STORAGE_ROOT,
                                                              self.project.organization_id,
                                                              self.project_id)
        if path.exists(local_path):
            rmtree(local_path, ignore_errors=True)
        return super(GitSSHRepository, self).delete(using, keep_parents)

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
        except NoSuchPathError:
            repo = None

        if repo is None:

            with tempfile.NamedTemporaryFile(delete=False) as temp:
                chmod(temp.name, 0o600)
                temp.write(base64.decodestring(self.private_key))

            env = {'GIT_SSH_COMMAND': 'ssh -i {} -o StrictHostKeyChecking=no'.format(temp.name)}

            repo = Repo.clone_from(
                url=self.url_repository_with_token(),
                to_path=repo_path,
                env=env,
                branch=ref,
                mirror=True
            )

        return repo

    def url_commit(self, sha):
        return ''

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

    def url_repository_with_token(self):
        return self.url_repository

    def get_hook_url(self):
        return '{domain}/api/ssh/hook/{proj_id}/'.format(domain=self.project.organization.site.domain,
                                                         proj_id=self.project_id)

    def receive_webhook(self, request, context, *args, **kwargs):
        from .events import event_push
        status, message = True, ''
        try:
            message = event_push(request.data, self.id)
        except Exception as exc:
            status, message = False, repr(exc)
        return status, message

    def handling_webhook(self, data=None):

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

    @staticmethod
    def processing_commits_fast(project, repository, data):
        return True
