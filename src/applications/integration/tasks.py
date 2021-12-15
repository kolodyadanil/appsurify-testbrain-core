# -*- coding: utf-8 -*-
from __future__ import absolute_import

from system.celery_app import app
from celery import group

# from celery_locked_task.locked_task import LockedTask

from datetime import datetime, timedelta

from applications.integration.utils import get_repository_model
from applications.integration.utils import processing_commits, processing_files, processing_rework

from applications.testing.utils.import_defects import import_defects

from applications.testing.utils.prediction.riskiness.fast_model import fast_model_analyzer
from applications.testing.utils.prediction.riskiness.slow_model import slow_model_analyzer

from applications.testing.utils.prediction.output.dispatcher import output_analyze


def make_clone_workflow(project_id, repository_id, model_name):
    workflow = clone_repository_task.signature(
        kwargs=dict(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            force=True
        ),
        immutable=True
    )

    workflow.link(
        fetch_repository_task.signature(
            kwargs=dict(
                project_id=project_id,
                repository_id=repository_id,
                model_name=model_name,
                data=None
            ),
            immutable=True
        )
    )

    processing_last_commits_workflow = make_processing_workflow(project_id=project_id, repository_id=repository_id,
                                                                model_name=model_name, data=None, since_time=2,
                                                                prefetch=False)

    processing_commits_workflow = make_processing_workflow(project_id=project_id, repository_id=repository_id,
                                                           model_name=model_name, data=None, since_time=None,
                                                           countdown=30, prefetch=False)

    workflow.link((processing_last_commits_workflow | processing_commits_workflow))
    return workflow


def make_processing_workflow(project_id, repository_id, model_name, data=None,
                             since_time=None, countdown=2, prefetch=True):
    workflow = fetch_repository_task.signature(
        kwargs=dict(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            data=data
        ),
        immutable=True
    )

    processing_commits_subtask = processing_commits_task.signature(
        kwargs=dict(
            project_id=project_id,
            repository_id=repository_id,
            model_name=model_name,
            data=data,
            since_time=since_time
        ),
        immutable=True,
        countdown=countdown
    )

    processing_commits_subtask.link((
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
        make_analytics_workflow(project_id=project_id, repository_id=repository_id, model_name=model_name)
    ))

    if prefetch:
        workflow.link(processing_commits_subtask)
    else:
        workflow = processing_commits_subtask

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
def clone_repository_task(self, project_id=None, repository_id=None, model_name=None, force=True):
    try:
        RepositoryModel = get_repository_model(model_name)
        repository = RepositoryModel.objects.get(id=repository_id)
        repository.clone_repository(force=force)
        return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True)
def fetch_repository_task(self, project_id=None, repository_id=None, model_name=None, data=None):
    try:
        RepositoryModel = get_repository_model(model_name)
        repository = RepositoryModel.objects.get(id=repository_id)

        refspec, before, after = None, None, None

        if data:
            webhook_data = repository.handling_push_webhook_payload(data=data)
            refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

        refs = repository.fetch_repository(refspec=refspec)
        return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True)
def processing_commits_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):

    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)

    refspec, before, after = None, None, None

    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    refs = repository.get_refs(refspec=refspec)
    result = processing_commits(task=self, project=repository.project, repository=repository,
                                refs=refs, before=before, after=after, since_time=since_time)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def processing_files_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)

    refspec, before, after = None, None, None

    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    refs = repository.get_refs(refspec=refspec)
    result = processing_files(task=self, project=repository.project, repository=repository,
                              refs=refs, before=before, after=after, since_time=since_time)

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def processing_rework_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)

    refspec, before, after = None, None, None

    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    refs = repository.get_refs(refspec=refspec)

    result = processing_rework(project=repository.project, repository=repository,
                              refs=refs, before=before, after=after, since_time=since_time)

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def processing_defects_task(self, project_id=None, repository_id=None, model_name=None, data=None, since_time=None):
    RepositoryModel = get_repository_model(model_name)
    repository = RepositoryModel.objects.get(id=repository_id)
    project = repository.project

    if project_id is None:
        project_id = repository.project_id

    refspec, before, after = None, None, None

    if data:
        webhook_data = repository.handling_push_webhook_payload(data=data)
        refspec, before, after = webhook_data['ref'], webhook_data['before'], webhook_data['after']

    corrective_commits = []

    refs = repository.get_refs(refspec=refspec)
    for ref in refs:
        commits = repository.get_commits(refspec=ref.name, before=before, after=after)
        if since_time:
            commits = filter(
                lambda commit:
                commit.committed_datetime.date() > (datetime.now() - timedelta(days=since_time)).date(),
                commits
            )

        corrective_commits.extend(map(lambda x: str(x.hexsha), commits))

    import_defects(project=project, repository=repository, corrective_commits=corrective_commits)

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
