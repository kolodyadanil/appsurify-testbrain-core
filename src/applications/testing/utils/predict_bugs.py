from sklearn.linear_model import LinearRegression
import pandas as pd
import os
import pickle
from applications.vcs.models import Commit
from django.conf import settings
from datetime import datetime, timedelta
import time
import math


def save_model(model, project_id):
    storage_path = settings.STORAGE_ROOT
    directory_path = os.path.join(storage_path, 'models', 'predict_bugs')
    model_path = os.path.join(directory_path, '%s.model' % project_id)

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    with open(model_path, 'wb') as outfile:
        pickle.dump(model, outfile)

    return model


def load_model(project_id):
    storage_path = settings.STORAGE_ROOT
    model_path = os.path.join(storage_path, 'models', 'predict_bugs', '%s.model' % project_id)

    if not os.path.exists(model_path):
        return None

    with open(model_path, 'rb') as infile:
        model = pickle.load(infile)

    return model


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

    ages = 0
    parents = commit.parents.all()

    for parent in parents:
        ages += time.mktime(parent.timestamp.timetuple())

    if parents:
        age = time.mktime(commit.timestamp.timetuple()) - (ages / len(parents))
    else:
        age = 0

    if total_string_changed:
        avg = float(files_count) / total_string_changed
        entropy = avg * math.log(avg, 2)
    else:
        entropy = 0

    commit_stats = {
        'hash': commit.sha[0:8],
        'deletions': commit.stats.get('deletions', 0),
        'additions': commit.stats.get('additions', 0),
        'total': commit.stats.get('total', 0),
        'dayofweek': commit.timestamp.weekday(),
        'hour': commit.timestamp.hour,
        'len_message': len(commit.message),
        'changed_files': files_count,
        'changed_directories': len(directories),
        'changed_subsystems': len(subsystems),
        'age': age,
        'entropy': entropy,
    }
    return commit_stats


def create_project_model(project_id):
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

    model = LinearRegression(copy_X=True, fit_intercept=True, n_jobs=1, normalize=False)
    model.fit(data_frame, labels)

    save_model(model=model, project_id=project_id)
    return model


def analyze_commits(project_id, commits_hashes=None):
    commits = []

    if commits_hashes:
        commits = Commit.objects.filter(project_id=project_id, sha__in=commits_hashes)

    if not commits_hashes:
        commits = Commit.objects.filter(project_id=project_id)

    if not commits:
        return False

    model = load_model(project_id=project_id)

    if not model:
        model = create_project_model(project_id=project_id)

    if not model:
        return False

    for commit in commits:
        commit_data = [
            get_commit_stats(commit)
        ]
        data_frame = pd.DataFrame(commit_data)
        data_frame = data_frame.set_index('hash').fillna(0)

        result = model.predict(X=data_frame)

        if len(result[0]) == 1:
            score = result[0][0]
        else:
            score = result[0][1]

        commit.riskiness = score
        # commit.output = score * 1000
        commit.save()

    return True
