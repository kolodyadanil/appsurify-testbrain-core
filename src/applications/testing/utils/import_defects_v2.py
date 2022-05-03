import re

from applications.project.models import Project
from applications.testing.models import Defect
from applications.vcs.models import Commit, Branch
from applications.vcs.utils.bugspots import DEFAULT_REGEX

search_regex = re.compile(DEFAULT_REGEX)


def get_buggy_commits_v2(corrective_commit):
    parents = corrective_commit.parents.exists()

    if parents:
        files = corrective_commit.parents.first().filechange_set.all()
    else:
        files = corrective_commit.filechange_set.all()

    buggy_commits = []

    for file in files:

        blame = file.blame
        blame_results = blame.split('\n\n')

        for blame_result in blame_results:
            blame_result = blame_result.splitlines()
            if len(blame_result) > 0:
                buggy_commit_sha = blame_result[0]

                if buggy_commit_sha not in buggy_commits:
                    buggy_commits.append(buggy_commit_sha)

    return buggy_commits


def import_defects_v2(project_id, corrective_commits=None):
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return False, 'Project not exists'

    if corrective_commits:
        # corrective_commits = [repo.commit(commit_hash) for commit_hash in corrective_commits]
        corrective_commits = Commit.objects.filter(project=project, sha__in=corrective_commits)
        corrective_commits = [commit for commit in corrective_commits if search_regex.match(commit.message)]

    if corrective_commits is None:
        corrective_commits = []

        for branch in Branch.objects.filter(project=project):

            commits = branch.commits.all()
            branch_corrective_commits = []

            for commit in commits:
                if search_regex.match(commit.message):
                    branch_corrective_commits.append(commit)

            corrective_commits += branch_corrective_commits

    for corrective_commit in corrective_commits:

        try:
            closed_commit = Commit.objects.filter(sha=corrective_commit.sha).last()
            if closed_commit is None:
                continue
        except Commit.DoesNotExist:
            continue

        try:
            defect = Defect.objects.filter(project_id=project_id, closed_commit=closed_commit).first()
            if defect is not None:
                continue
        except Defect.DoesNotExist:
            pass

        buggy_commits = get_buggy_commits_v2(corrective_commit=corrective_commit)

        if not buggy_commits:
            continue

        # commit_date = datetime.fromtimestamp(corrective_commit.timestamp, tz=pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        commit_date = corrective_commit.timestamp

        defect = Defect()
        defect.closed_commit = closed_commit
        defect.error = corrective_commit.message
        defect.close_date = commit_date
        defect.project_id = project_id

        defect.priority = 10

        defect.create_type = Defect.CREATE_TYPE_GIT_IMPORT
        defect.type = Defect.TYPE_PROJECT
        defect.close_type = Defect.CLOSE_TYPE_FIXED

        defect.status = Defect.STATUS_CLOSED
        defect.severity = Defect.SEVERITY_TRIVIAL

        defect.found_date = corrective_commit.timestamp
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
