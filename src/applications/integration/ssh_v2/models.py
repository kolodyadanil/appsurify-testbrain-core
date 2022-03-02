# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import sleep

import os
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()
ref_pattern = re.compile(
    r"(^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)|/head(s)?|\d+/head(s)?|/merge(s)?|\d+/merge(s)?|\.lock)")


class GitSSHv2Repository(models.Model):
    project = models.OneToOneField('project.Project', related_name='git_ssh_v2_repository', null=False,
                                   on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='git_ssh_v2_repository', null=False, on_delete=models.CASCADE)

    repository_name = models.CharField(max_length=255, blank=False, null=False)
    is_installed_hook = models.BooleanField(default=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        unique_together = ('user', 'repository_name')
        verbose_name = 'Git SSH v2 repository'
        verbose_name_plural = 'Git SSH v2 repositories'

    def __str__(self):
        return '{}/{}'.format(self.user.username, self.repository_name)

    def url_commit(self, sha):
        return ''

    def url_repository_with_token(self):
        return ''

    def clone_repository(self, force=False):
        return True

    def pull_repository(self):
        return True

    def receive_webhook(self, request, context, *args, **kwargs):
        from .events import event_install, event_commit, event_tag, event_delete
        events = {
            'install': event_install,
            'push': event_commit,
            'create': event_tag,
            # 'delete': event_delete,
        }
        status, message = True, ''

        event = request.META.get('HTTP_X_GIT_EVENT')

        if event == 'ping':
            status, message = True, 'OK'
            return status, message

        event_func = events.get(event)
        if event_func is None:
            status, message = False, 'Unsupported webhook event.'

        try:
            message = event_func(request.data, self.id)
        except Exception as exc:
            status, message = False, repr(exc)

        return status, message

    def generate_webhook(self, request, context, *args, **kwargs):
        from applications.api.external.utils import ConfirmationHMAC
        from django.urls import reverse
        from .hook import generate_hook

        repo_name = self.repository_name
        username = self.user.username
        project = self.project

        organization = project.organization
        api_key = ConfirmationHMAC(organization).key

        hook_url = request.build_absolute_uri(reverse('hook-receive', args=('ssh_v2', project.id,)))
        hook = generate_hook(hook_url, username, repo_name, api_key)
        return hook
