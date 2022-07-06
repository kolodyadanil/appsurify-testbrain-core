import pytz
import math
import time
import logging

from collections import Counter
from datetime import datetime
from dateutil.relativedelta import relativedelta

from applications.project.models import Project
from applications.ml.network import SlowCommitRiskinessRFCM
from applications.vcs.models import Commit


def update_slow_commits_metrics(project_id):
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return False, 'Project not exists'

    from_datetime = datetime.now() + relativedelta(weeks=-4)  # TODO: Change!!!
    from_datetime = from_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

    commits = Commit.objects.filter(project_id=project_id, timestamp__gte=from_datetime)

    # branches = project.branches.all()
    #
    # for branch in branches:
    #
    #     commits = branch.commits.filter(timestamp__gte=from_datetime)

    for db_commit in commits.order_by('timestamp'):

        files = {}
        dev_experience = {}

        commit_date = db_commit.timestamp

        author_name = db_commit.author.get('name')

        if not author_name:
            author_name = db_commit.author.get('email')

        total_lines_modified = db_commit.stats['total']

        line_added = db_commit.stats['additions']

        line_deleted = db_commit.stats['deletions']

        files_modified = db_commit.filechange_set.count()

        entropy = 0
        age = 0

        developers = 1 + Counter(db_commit.message.split()).get('Co-authored-by:', 0)

        files_unique_changes = 0
        total_changes_before_commit = 0
        experience_weight = 0
        author_changes = 0
        author_changes_subsystem = 0

        directories = {}
        subsystems = {}
        files_strings_modified = []

        for file_item in db_commit.filechange_set.values('additions', 'deletions', 'changes',
                                                         'file__full_filename'):
            file_path = file_item['file__full_filename']

            stats = {
                'lines': file_item['changes']
            }

            # Original
            path_elements = file_path.split('/')

            last_file_changes = files.get(file_path, {})

            if not last_file_changes:
                files[file_path] = {}

            last_change = last_file_changes.get('last_change', commit_date)
            last_unique_changes = last_file_changes.get('unique_changes', 0)
            last_files_strings = last_file_changes.get('last_files_strings', 0)

            if not last_unique_changes:
                files[file_path]['unique_changes'] = 0

            total_changes_before_commit += last_files_strings

            files_unique_changes += last_unique_changes

            if len(path_elements) == 1:
                directory = 'root'
                subsystem = 'root'
            else:
                directory = '/'.join(path_elements[0:-1])
                subsystem = path_elements[0]

            directories[directory] = 1
            subsystems[subsystem] = 1

            author_experiences = dev_experience.get(author_name)

            if author_experiences:
                experiences = dev_experience[author_name]
                author_changes += sum(experiences.values())

                if subsystem in experiences:
                    author_changes_subsystem = experiences[subsystem]
                    experiences[subsystem] += 1
                else:
                    experiences[subsystem] = 1

            else:
                dev_experience[author_name] = {subsystem: 1}

            files[file_path]['last_change'] = commit_date
            files[file_path]['total_modified'] = stats.get('lines')
            files[file_path]['authors'] = developers
            files[file_path]['unique_changes'] += 1
            files[file_path]['last_files_strings'] = last_files_strings + db_commit.stats['additions'] - \
                                                     db_commit.stats['deletions']

            files_strings_modified.append(stats.get('lines'))

            age += float((commit_date - last_change).seconds) / 86400

            if age != 0:
                experience_weight += (1 / (age + 1))
            else:
                experience_weight = 0

        for file_modifies in files_strings_modified:
            if file_modifies:
                try:
                    avg = float(file_modifies) / total_lines_modified
                    entropy -= (avg * math.log(avg, 2))
                except ZeroDivisionError:
                    continue

        if not files_modified:
            continue

        lines_code_before_commit = float(total_changes_before_commit) / files_modified

        age = age / files_modified

        author_changes = float(author_changes) / files_modified
        author_changes_subsystem = author_changes_subsystem / files_modified

        modified_subsystems = len(subsystems)
        modified_directories = len(directories)

        commit_stats = {
            'additions': line_added,
            'deletions': line_deleted,
            'total_lines_modified': total_lines_modified,
            'lines_code_before_commit': lines_code_before_commit,
            'changed_subsystems': modified_subsystems,
            'changed_directories': modified_directories,
            'changed_files': files_modified,
            'developers': developers,
            'files_unique_changes': files_unique_changes,
            'author_changes': author_changes,
            'experience_weight': experience_weight,
            'author_changes_subsystem': author_changes_subsystem,
            'entropy': entropy,
            'age': age,
        }

        db_commit.stats['slow_model'] = commit_stats
        db_commit.save()

    return True



def slow_model_analyzer(project_id, commits_hashes=None):
    update_slow_commits_metrics(project_id=project_id)

    try:
        fcr_rfcm = SlowCommitRiskinessRFCM(project_id=project_id)
        fcr_rfcm = fcr_rfcm.train()

        riskiness_commits = fcr_rfcm.predict_to_riskiness(commit_sha_list=commits_hashes)

        for sha, riskiness in riskiness_commits.items():
            Commit.objects.filter(sha=sha).update(riskiness=riskiness)

    except Exception as exc:
        logging.exception(f"Some error for slow model analyzer")
        raise exc
