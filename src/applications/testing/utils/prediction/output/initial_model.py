# -*- coding: utf-8 -*-
import os
import pickle
from datetime import datetime, timedelta

import pandas as pd
from django.conf import settings
from sklearn.linear_model import LinearRegression

from applications.vcs.models import Commit


def get_commit_stats(commit):
    files_count = commit.files.count()
    total_string_changed = commit.stats.get('total', 0)

    directories = {}
    subsystems = {}

    for commit_file in commit.files.all():
        path_elements = commit_file.full_filename.split('/')

        if commit_file.sha:
            if len(path_elements) == 1:
                directories['root'] = 1
                subsystems['root'] = 1
            else:
                directories['/'.join(path_elements[0:-1])] = 1
                subsystems[path_elements[0]] = 1

    commit_stats = {
        'hash': commit.sha[0:8],
        'deletions': commit.stats.get('deletions', 0),
        'additions': commit.stats.get('additions', 0),
        'total_lines_modified': total_string_changed,
        'changed_files': files_count,
        'changed_directories': len(directories),
        'changed_subsystems': len(subsystems),
    }
    return commit_stats


def create_initial_output_model(project_id):
    date_limit = datetime.now() - timedelta(weeks=2)
    commits = Commit.objects.filter(project_id=project_id, timestamp__lte=date_limit).prefetch_related(
        'founded_defects', 'files', 'parents')

    if not commits:
        return False

    commits_data = []
    buggy_commits = []

    for commit in commits:
        commit_stats = get_commit_stats(commit)
        commits_data.append(commit_stats)

        if commit.caused_defects.count():
            buggy_commits.append(commit.sha[0:8])

    data_frame = pd.DataFrame(commits_data)
    data_frame = data_frame.set_index('hash').fillna(0)

    labels = data_frame.index.isin(buggy_commits).astype(int)
    labels = pd.Series(data=labels, index=data_frame.index, name='label')

    model = LinearRegression()
    model.fit(data_frame, labels)

    base_path = settings.BASE_DIR
    directory_path = os.path.join(base_path, 'applications', 'testing', 'tools')
    model_path = os.path.join(directory_path, 'initial_output.model')

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    outfile = open(model_path, 'wb')
    pickle.dump(model, outfile, protocol=pickle.HIGHEST_PROTOCOL)

    return model


def initial_output_model_analyzer(project_id, commits_hashes=None):
    base_path = settings.BASE_DIR
    model_path = os.path.join(base_path, 'applications', 'testing', 'tools', 'initial_output.model')

    if not os.path.exists(model_path):
        model = create_initial_output_model(project_id=project_id)

        if not model:
            return False

    with open(model_path, 'rb') as infile:
        model = pickle.load(infile)

    if not model:
        return False

    commits = []

    if commits_hashes:
        commits = Commit.objects.filter(project_id=project_id, sha__in=commits_hashes)

    if not commits_hashes:
        commits = Commit.objects.filter(project_id=project_id)

    if not commits:
        return False

    for commit in commits:
        commit_stats = get_commit_stats(commit)
        commit_data = [
            commit_stats,
        ]
        data_frame = pd.DataFrame(commit_data)
        data_frame = data_frame.set_index('hash').fillna(0)
        coefficients_data_frame = pd.DataFrame(model.coef_, data_frame.columns, columns=['coefficient'])
        coefficients = coefficients_data_frame.to_dict().get('coefficient', {})

        output = 0

        for metric, value in coefficients.items():
            coefficient_metric = value * commit_stats.get(metric)
            output += coefficient_metric

        if output < 0:
            output = -output

        output = output * 1000
        output += commit_stats.get('total_lines_modified')
        if output > 1000:
            output = 1000

        Commit.objects.filter(pk=commit.id).update(output=output)

    return True
