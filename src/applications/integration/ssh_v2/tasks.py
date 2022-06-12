# -*- coding: utf-8 -*-
from system.celery_app import app

from applications.vcs.models import Commit
from applications.integration.utils import get_repository_model

from applications.integration.ssh_v2.utils import sync_full_commits
from applications.integration.ssh_v2.utils import processing_commit_file_v2
from applications.integration.ssh_v2.utils import calculate_rework_one_commit_v2

from applications.testing.utils.prediction.riskiness.fast_model import fast_model_analyzer
from applications.testing.utils.prediction.riskiness.slow_model import slow_model_analyzer
from applications.testing.utils.prediction.output.dispatcher import output_analyze
from applications.testing.utils.import_defects_v2 import import_defects_v2


@app.task(bind=True)
def fetch_commits_task_v2(self, project_id=None, repository_id=None, model_name=None, data=None):
    from applications.integration.ssh_v2.utils import commits_processed

    if data is None:
        data = {}

    processed = commits_processed(repository_id=repository_id, data=data)
    if processed:
        return

    RepositoryModel = get_repository_model('gitsshv2repository')
    repository = RepositoryModel.objects.get(pk=repository_id)
    queue = self.request.delivery_info["routing_key"]

    new_commits_sha = sync_full_commits(project=repository.project, repository=repository, data=data)

    processing_commit_file_task_v2.apply_async(
        args=[],
        kwargs={
            "project_id": project_id,
            "repository_id": repository_id,
            "model_name": model_name,
            "data": data,
            "commits_sha": new_commits_sha,
        },
        queue=queue,
    )

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def processing_commit_file_task_v2(self, project_id=None, repository_id=None, model_name=None, data=None, commits_sha=None):

    if commits_sha is None:
        commits_sha = []

    RepositoryModel = get_repository_model('gitsshv2repository')
    repository = RepositoryModel.objects.get(pk=repository_id)

    file_list = []

    file_list = processing_commit_file_v2(project=repository.project, repository=repository, data=data)

    if len(file_list) > 0:
        calculate_rework_task_v2.delay(project_id=project_id, repository_id=repository_id, model_name=model_name,
                                       commits_sha=commits_sha)

    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def calculate_rework_task_v2(self, project_id=None, repository_id=None, model_name=None, commits_sha=None):

    if commits_sha is None:
        commits_sha = []

    queryset = Commit.objects.filter(project_id=project_id, sha__in=commits_sha)

    total_count = queryset.count()
    success_count = 0
    failure_count = 0

    for commit_id in queryset.values_list('id', flat=True).iterator():
        result = calculate_rework_one_commit_v2(commit_id)

        if result:
            success_count += 1
        else:
            failure_count += 1

    import_defects_task_v2.delay(project_id=project_id, repository_id=repository_id, model_name=model_name,
                                 commits_sha=commits_sha)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def import_defects_task_v2(self, project_id=None, repository_id=None, model_name=None, commits_sha=None):

    if commits_sha is None:
        commits_sha = []

    import_defects_v2(project_id, corrective_commits=commits_sha)

    fast_model_analyzer_task.delay(project_id=project_id, repository_id=repository_id, model_name=model_name)
    slow_models_analyzer_task.delay(project_id=project_id, repository_id=repository_id, model_name=model_name)
    output_analyse_task.delay(project_id=project_id, repository_id=repository_id, model_name=model_name)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def fast_model_analyzer_task(self, project_id=None, repository_id=None, model_name=None):
    fast_model_analyzer(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def slow_models_analyzer_task(self, project_id=None, repository_id=None, model_name=None):
    slow_model_analyzer(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}


@app.task(bind=True)
def output_analyse_task(self, project_id=None, repository_id=None, model_name=None):
    output_analyze(project_id=project_id)
    return {'project_id': project_id, 'repository_id': repository_id, 'model_name': model_name}
