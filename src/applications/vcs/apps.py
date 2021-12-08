# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import pre_migrate
from django.db.transaction import atomic

def delete_duplicated_sha(**kwargs):
    from django.db.models import Count
    from applications.vcs.models import Commit, FileChange

    try:
        print('  Delete duplicated commits...')
        print('    Perform queryset for commits...')
        qs = Commit.objects.all().values('project', 'sha').annotate(
            cnt=Count('sha')).filter(cnt__gt=1).values_list('sha', flat=True)
        print('    Duplicated commits: {}'.format(len(list(qs))))
        with atomic():
            for sha in qs:
                Commit.objects.filter(sha=sha).order_by('created').first().delete()
        print('  Done delete duplicated commits.')

        print('  Delete duplicated filechanges...')
        print('    Perform queryset for filechanges...')
        qs = FileChange.objects.all().values('commit_id', 'file_id').annotate(
            cnt=Count('file_id')).filter(cnt__gt=1).values_list('file_id', flat=True)
        print('    Duplicated filechanges: {}'.format(len(list(qs))))
        with atomic():
            for file_id in qs:
                FileChange.objects.filter(file_id=file_id).order_by('created').first().delete()
        print('  Done delete duplicated filechanges.')

    except Exception as exc:
        print(' Re-try migration one more time.')


class VCSConfig(AppConfig):
    name = 'applications.vcs'
    verbose_name = _('VCS (Version Control System)')
    
    # def ready(self):
    #     import signals
    #     pre_migrate.connect(delete_duplicated_sha, sender=self)
