# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .api import create_web_hook, delete_web_hook, refresh_bitbucket_token
from .models import BitbucketHook, BitbucketRepository


@receiver(post_save, sender=BitbucketRepository)
def model_repos_create_hook(sender, instance, created, **kwargs):
    repo = instance
    bitbucket_repo_name = repo.bitbucket_repository_name
    domain = repo.project.organization.site.domain

    if created:
        access_token = repo.get_or_refresh_token()
        response = create_web_hook(repository_full_name=bitbucket_repo_name, access_token=access_token, domain=domain, project_id=repo.project_id)

        if response.status_code == 201:
            response = response.json()
            BitbucketHook.objects.create(project_id=repo.project_id, id_hook=response.get('uuid'), created_at=response.get('created_at'), updated_at=response.get('created_at'))


@receiver(post_delete, sender=BitbucketRepository)
def model_repos_delete_hook(sender, instance, **kwargs):
    repo = instance

    try:
        hook = BitbucketHook.objects.get(project_id=repo.project_id)
    except BitbucketHook.DoesNotExist:
        return

    token = repo.get_or_refresh_token()
    delete_web_hook(repository_full_name=repo.bitbucket_repository_name, access_token=token, id_hook=hook.id_hook)
    hook.delete()
