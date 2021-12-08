import math
import time
from datetime import datetime, timedelta

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from applications.testing.utils.prediction.common import save_model, load_model
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

    ages = 0
    parents = commit.parents.all()

    for parent in parents:
        ages += time.mktime(parent.timestamp.timetuple())

    if parents:
        age = time.mktime(commit.timestamp.timetuple()) - (ages / len(parents))
    else:
        age = 0

    try:
        avg = float(files_count) / total_string_changed
        entropy = avg * math.log(avg, 2)
    except:
        entropy = 0

    commit_stats = {
        'hash': commit.display_id,
        'deletions': commit.stats.get('deletions', 0),
        'additions': commit.stats.get('additions', 0),
        'total_lines_modified': commit.stats.get('total', 0),
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


def create_fast_model(project_id):
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
            buggy_commits.append(commit.display_id)

    data_frame = pd.DataFrame(commits_data)
    data_frame = data_frame.set_index('hash').fillna(0)

    labels = data_frame.index.isin(buggy_commits).astype(int)
    labels = pd.Series(data=labels, index=data_frame.index, name='label')

    model = RandomForestClassifier(n_jobs=-1, max_features='sqrt', n_estimators=200, oob_score=True)
    model.fit(data_frame, labels)

    save_model(model=model, project_id=project_id, model_prefix='fast_riskiness')
    return model


def fast_model_analyzer(project_id, commits_hashes=None):
    model = load_model(project_id=project_id, model_prefix='fast_riskiness')

    if not model:
        model = create_fast_model(project_id=project_id)

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
        commit_data = [
            get_commit_stats(commit)
        ]
        data_frame = pd.DataFrame(commit_data)
        data_frame = data_frame.set_index('hash').fillna(0)

        result = model.predict_proba(X=data_frame)

        if len(result[0]) == 1:
            score = result[0][0]
        else:
            score = result[0][1]

        Commit.objects.filter(pk=commit.id).update(riskiness=score)

    return True
