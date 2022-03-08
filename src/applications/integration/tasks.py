# -*- coding: utf-8 -*-
from __future__ import absolute_import

import time

from git import GitCommandError

from system.celery_app import app
from celery import group

from datetime import datetime, timedelta

from applications.integration.utils import get_repository_model
from applications.integration.utils import processing_commits, processing_files, processing_rework

from applications.testing.utils.import_defects import import_defects

from applications.testing.utils.prediction.riskiness.fast_model import fast_model_analyzer
from applications.testing.utils.prediction.riskiness.slow_model import slow_model_analyzer

from applications.testing.utils.prediction.output.dispatcher import output_analyze


def make_clone_workflow(project_id, repository_id, model_name):
    workflow = make_processing_workflow(project_id, repository_id, model_name, data=None, since_time=2)
    processing_commits_workflow = make_processing_workflow(project_id=project_id, repository_id=repository_id,
                                                           model_name=model_name, data=None, since_time=None)

    workflow.link(processing_commits_workflow)
    return workflow


def make_processing_workflow(project_id, repository_id, model_name, data=None, since_time=None):
    common_workflow = processing_commits_task.signature(
        kwargs=dict(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            data=data,
            since_time=since_time
        ),
        immutable=True
    )

    common_workflow.link((
        processing_files_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name,
                data=data,
                since_time=since_time
            ),
            immutable=True
        ) |
        processing_rework_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name,
                data=data,
                since_time=since_time
            ),
            immutable=True
        ) |
        processing_defects_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name,
                data=data,
                since_time=since_time
            ),
            immutable=True
        ) |
        make_analytics_workflow(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            data=data,
            since_time=since_time
        )
    ))

    fast_workflow = processing_commits_fast_task.signature(
        kwargs=dict(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            data=data
        ),
        immutable=True
    )

    workflow = (fast_workflow | common_workflow)
    return workflow


def make_analytics_workflow(project_id, repository_id, model_name, data=None, since_time=None, countdown=2):
    workflow = group(
        analyze_fast_model_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name
            ),
            immutable=True
        ),
        analyze_slow_models_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name
            ),
            immutable=True
        ),
        analyze_output_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name
            ),
            immutable=True
        ),
    )
    return workflow


@app.task(bind=True)
def processing_commits_fast_task(self, project_id=None, repository_id=None, model_name=None, data=None):
    try:
        RepositoryModel = get_repository_model(model_name)
        repository = RepositoryModel.objects.get(id=repository_id)

        result = repository.processing_commits_fast(project=repository.project, repository=repository, data=data)

        return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True)
def processing_commits_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    try:
        RepositoryModel = get_repository_model(model_name)
        repository = RepositoryModel.objects.get(id=repository_id)

        ref, before, after = None, None, None
        if data:
            webhook_data = repository.handling_push_webhook_payload(data=data)
            refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

        result = processing_commits(project=repository.project, repository=repository,
                                    ref=ref, before=before, after=after, since_time=since_time)
        return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True)
def processing_files_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    try:
        RepositoryModel = get_repository_model(model_name)
        repository = RepositoryModel.objects.get(id=repository_id)

        ref, before, after = None, None, None
        if data:
            webhook_data = repository.handling_push_webhook_payload(data=data)
            ref, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

        result = processing_files(project=repository.project, repository=repository,
                                  ref=ref, before=before, after=after, since_time=since_time)

        return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True)
def processing_rework_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)

    ref, before, after = None, None, None
    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        ref, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    result = processing_rework(project=repository.project, repository=repository,
                               ref=ref, before=before, after=after, since_time=since_time)

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def processing_defects_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)
    project = repository.project

    ref, before, after = None, None, None
    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        ref, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    repo = repository.get_repo(ref=ref, before=before, after=after)

    corrective_commits = []

    refs = []
    if ref is None:
        refs = repository.get_refs()
    else:
        refs = [ref, ]

    for refspec in refs:
        commits = repository.get_commits(ref=ref, before=before, after=after, refspec=refspec)
        if since_time:
            try:
                commits = filter(
                    lambda commit:
                    commit.committed_datetime.date() > (datetime.now() - timedelta(days=since_time)).date(),
                    commits
                )
            except ValueError:
                pass

        corrective_commits.extend(map(lambda x: str(x.hexsha), commits))

    import_defects(project=project, repository=repository, repo=repo, corrective_commits=corrective_commits)

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def analyze_fast_model_task(self, project_id=None, repository_id=None, model_name=None):
    result = fast_model_analyzer(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def analyze_slow_models_task(self, project_id=None, repository_id=None, model_name=None):
    result = slow_model_analyzer(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def analyze_output_task(self, project_id=None, repository_id=None, model_name=None):
    result = output_analyze(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
