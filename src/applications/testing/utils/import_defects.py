import pytz
import re
from datetime import datetime

from git import Repo, GitCommandError

from django.conf import settings

from applications.project.models import Project
from applications.testing.models import Defect
from applications.vcs.models import Branch, Commit
from applications.vcs.utils.bugspots import DEFAULT_REGEX


search_regex = re.compile(DEFAULT_REGEX)


def get_buggy_commits(repo, corrective_commit):
    parents = corrective_commit.parents

    if parents:
        diffs = corrective_commit.diff(parents[0], create_patch=True, unified=0)
    else:
        diffs = corrective_commit.diff(create_patch=True, unified=0)

    buggy_commits = []

    for diff in diffs:
        file_path = diff.a_path

        if not file_path:
            continue

        patch = diff.diff
        patch_strings = patch.split('\n')

        current_string_number = 0
        previous_number = 0
        group = []
        groups = []

        for string in patch_strings:

            if '@@' in string:
                try:
                    current_string_number = abs(int(string.split(' @@ ')[0].split('@@ ')[-1].split(' ')[0].split(',')[0]))
                except:
                    continue
            else:
                if string.startswith('-'):
                    if current_string_number - previous_number == 1:
                        group.append(current_string_number)
                    else:
                        groups.append(group)
                        group = [current_string_number]

                    previous_number = current_string_number

                current_string_number += 1
        groups.append(group)

        for string_group in groups:
            if not string_group:
                continue

            try:
                blame_results = repo.blame(None, file_path, L='%s,%s' % (string_group[0], string_group[-1]), C=corrective_commit.hexsha + '^')
            except GitCommandError:
                continue

            for blame in blame_results:
                buggy_commit_sha = blame[0].hexsha

                if buggy_commit_sha not in buggy_commits:
                    buggy_commits.append(buggy_commit_sha)

    return buggy_commits


def import_defects(project=None, repository=None, repo=None, corrective_commits=None):

    if project is None:
        project = repository.project

    refs = repository.get_refs()

    if corrective_commits:
        corrective_commits = [repo.commit(commit_hash) for commit_hash in corrective_commits]
        corrective_commits = [commit for commit in corrective_commits if search_regex.match(commit.message)]

    if corrective_commits is None:
        corrective_commits = []

        for refspec in refs:

            commits = repo.iter_commits(rev=refspec)

            branch_corrective_commits = []

            for commit in commits:
                if search_regex.match(commit.message):
                    branch_corrective_commits.append(commit)

            corrective_commits += branch_corrective_commits

    for corrective_commit in corrective_commits:

        try:
            closed_commit = Commit.objects.filter(sha=corrective_commit.hexsha).last()
            if closed_commit is None:
                continue
        except Commit.DoesNotExist:
            continue

        try:
            defect = Defect.objects.filter(project=project, closed_commit=closed_commit).first()
            if defect is not None:
                continue
        except Defect.DoesNotExist:
            pass

        buggy_commits = get_buggy_commits(repo=repo, corrective_commit=corrective_commit)

        if not buggy_commits:
            continue

        commit_date = datetime.fromtimestamp(corrective_commit.committed_date, tz=pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

        defect = Defect()
        defect.closed_commit = closed_commit
        defect.error = corrective_commit.message
        defect.close_date = commit_date
        defect.project = project

        defect.priority = 10

        defect.create_type = Defect.CREATE_TYPE_GIT_IMPORT
        defect.type = Defect.TYPE_PROJECT
        defect.close_type = Defect.CLOSE_TYPE_FIXED

        defect.status = Defect.STATUS_CLOSED
        defect.severity = Defect.SEVERITY_TRIVIAL

        defect.found_date = datetime.fromtimestamp(corrective_commit.authored_date, tz=pytz.UTC)
        defect.save()

        caused_by_commits = Commit.objects.filter(sha__in=buggy_commits, project=project)
        defect.caused_by_commits = caused_by_commits

        fixing_commit_number = closed_commit.display_id
        bug_commit_number = ','.join([bug_commit.display_id for bug_commit in caused_by_commits])

        name = 'Defect created from {bug_commit_number} and fixed by {fixing_commit_number}'.format(
            bug_commit_number=bug_commit_number, fixing_commit_number=fixing_commit_number)
        defect.name = name[:255]
        defect.description = name

        defect.reason = '|'.join([bug_commit.message for bug_commit in caused_by_commits])[0:255]

        defect.save()

    return True


