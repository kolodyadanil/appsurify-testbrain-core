# -*- coding: utf-8 -*-
from __future__ import absolute_import
from system.celery_app import app, Singleton

from django.core.exceptions import ObjectDoesNotExist

from applications.project.models import Project
from applications.vcs.models import Area
from celery import shared_task


@shared_task
def create_area_from_folders_task():
    projects = Project.objects.all()
    ids = list()
    for project in projects:
        Area.create_from_folders(project.id)
        ids.append(project.id)
    return f'Area is auto generated for projects {ids}'


@app.task(base=Singleton, raise_on_duplicate=False, lock_expiry=10 * 60)
def clean_duplicates_from_vcs(*args, **kwargs):
    from django.db.transaction import atomic
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
