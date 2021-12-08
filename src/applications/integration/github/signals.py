# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .api import create_web_hook, delete_web_hook
from .models import GithubHook, GithubRepository


@receiver(post_save, sender=GithubRepository)
def model_repos_create_hook(sender, instance, created, **kwargs):
    repo = instance
    github_repo_name = repo.github_repository_name
    domain = repo.project.organization.site.domain
    if created:
        try:
            access_token = repo.token
            response = create_web_hook(repository_full_name=github_repo_name, access_token=access_token, domain=domain,
                                       project_id=repo.project_id)
            if response.status_code == 201:
                response = response.json()
                GithubHook.objects.create(
                    project_id=repo.project_id,
                    id_hook=response.get('id'),
                    created_at=response.get('created_at'),
                    updated_at=response.get('updated_at')
                )
        except Exception:
            pass

@receiver(post_delete, sender=GithubRepository)
def model_repos_delete_hook(sender, instance, **kwargs):
    repo = instance
    access_token = repo.token
    try:
        hook = GithubHook.objects.get(project_id=repo.project_id)
        delete_web_hook(
            repository_full_name=repo.github_repository_name,
            access_token=access_token,
            id_hook=hook.id_hook
        )
        hook.delete()
    except GithubHook.DoesNotExist:
        pass
    except Exception:
        pass
