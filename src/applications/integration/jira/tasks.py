# -*- coding: utf-8 -*-
from __future__ import absolute_import
from system.celery_app import app
from applications.project.models import Project
from .models import *


@app.task(bind=True, retry_kwargs={'max_retries': 3}, retry_backoff=True)
def jira_pull_issues_task(self, project=None, force_update=False):
    status = 'failure'
    jp = JiraProject.objects.get(project_id=project)
    result = JiraProject.pull_issues(project=jp, force_update=force_update)
    if result:
        status = 'successful'
    return {'status': status, 'project_id': project, 'jira_project_id': jp.id}


@app.task(bind=True, retry_kwargs={'max_retries': 3}, retry_backoff=True)
def jira_push_issues_task(self, project=None, force_update=False):
    status = 'failure'
    jp = JiraProject.objects.get(project_id=project)
    result = JiraProject.push_issues(project=jp, force_update=force_update)
    if result:
        status = 'successful'
    return {'status': status, 'project_id': project, 'jira_project_id': jp.id}

