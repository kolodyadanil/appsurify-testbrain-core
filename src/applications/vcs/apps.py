# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import pre_migrate
from django.db.transaction import atomic


def delete_duplicated_sha(**kwargs):
    from django.db.models import Count
    from applications.vcs.models import Commit, FileChange
    from django.db import connection
    c = connection.cursor()
    try:
        print('  Delete duplicated commits...')
        c.execute("""
DELETE FROM vcs_commit
WHERE id IN (
    SELECT id
    FROM (
            SELECT id,
                ROW_NUMBER() OVER( PARTITION BY sha, project_id ORDER BY id) AS DuplicateCount
            FROM vcs_commit ORDER BY id) vc
            WHERE vc.DuplicateCount > 1
);
        """)
        print('  Done delete duplicated commits.')
        print('  Delete duplicated filechanges...')
        c.execute("""
DELETE FROM vcs_filechange
WHERE id IN (
    SELECT id
    FROM (
            SELECT id,
                ROW_NUMBER() OVER( PARTITION BY file_id, commit_id ORDER BY id) AS DuplicateCount
            FROM vcs_filechange ORDER BY id) vfc
            WHERE vfc.DuplicateCount > 1
);
        """)
        print('  Done delete duplicated filechanges.')
    except Exception as e:
        print("Some error on cleanup duplicates")
    finally:
        c.close()


class VCSConfig(AppConfig):
    name = 'applications.vcs'
    verbose_name = _('VCS (Version Control System)')
    
    def ready(self):
        import applications.vcs.signals
        pre_migrate.connect(delete_duplicated_sha, sender=self)
