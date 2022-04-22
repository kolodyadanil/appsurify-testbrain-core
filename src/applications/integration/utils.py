# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import time
import re
from datetime import datetime, timedelta
from django.apps import apps as django_apps
from django.conf import settings
from django.db import models
from git import GitCommandError

from applications.vcs.models import Commit, Branch, File, FileChange, Area


mtime = time.time
sleep = time.sleep

filename_regex = re.compile(r'\{.*\s=>\s.*\}')

ref_pattern = re.compile(r"^(refs/(remotes/|heads/)(origin/)?|remotes/(origin/)?|origin/)")

patch_re = re.compile(
    '^@@ -(?P<start_orig>[0-9]+),(?P<end_orig>[0-9]+) \+(?P<start_new>[0-9]+),(?P<end_new>[0-9]+) @@',
    re.MULTILINE)

output_re = re.compile(
    '^.+ \((?P<author_name>.*) (?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}) (?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2}) .(?P<tz>[0-9]{4}) (?P<lines>.*)\) (?P<data>.*)',
    re.MULTILINE)

FNULL = open(os.devnull, 'w')


def get_repository_model(model_name):
    """
    Returns the User model that is active in this project.
    """
    map = {
        'gitrepository': 'git_integration.GitRepository',
        'bitbucketrepository': 'bitbucket_integration.BitbucketRepository',
        'githubrepository': 'github_integration.GitHubRepository',
        'perforcerepository': 'perforce_integration.PerforceRepository',
        'gitsshrepository': 'git_ssh_integration.GitSSHRepository',
        'gitsshv2repository': 'git_ssh_v2_integration.GitSSHv2Repository'
    }
    return django_apps.get_model(map.get(model_name), require_ready=False)


def get_diff_type(diff):
    if diff.renamed:
        return 'R'
    if diff.deleted_file:
        return 'D'
    if diff.new_file:
        return 'A'
    return 'M'


def prepare_path(path):

    path = path.replace('"', '')

    if '=>' not in path:
        return path

    if filename_regex.findall(path):
        extracted_filename = filename_regex.search(path).group()
        correct_filename = extracted_filename.split('=> ')[-1].rstrip('}')

        path = path.replace(extracted_filename, correct_filename)
    else:
        path = path.split(' => ')[-1]

    path = os.path.normpath(path)
    return path


def processing_commits(project=None, repository=None, ref=None, before=None, after=None, since_time=None):

    repo = repository.get_repo(ref=ref, before=before, after=after, force=True)

    if project is None:
        project = repository.project

    if ref is None:
        refs = repository.get_refs()
    else:
        refs = [ref, ]

    new_commits = []

    for refspec in refs:

        branch, _ = Branch.objects.get_or_create(project=project, name=refspec)
        try:
            commits = repository.get_commits(ref=ref, before=before, after=after, refspec=refspec)
        except GitCommandError:
            continue

        if since_time:
            commits = filter(
                lambda commit:
                commit.committed_datetime.date() > (datetime.now() - timedelta(days=since_time)).date(),
                commits
            )

        for commit in commits:
            new_commit, _ = create_or_update_commit(project=repository.project, repository=repository, branch=branch,
                                                    refspec=refspec, commit=commit)
            new_commits.append(new_commit)

        # db_exist_commits = list(
        #     Commit.objects.filter(
        #         project=project,
        #         sha__in=map(lambda x: str(x.hexsha), commits)).values_list('sha', flat=True)
        # )
        #
        # for commit in filter(lambda x: str(x.hexsha) not in db_exist_commits, commits):
        #     new_commit, _ = create_or_update_commit(project=repository.project, repository=repository, branch=branch,
        #                                             refspec=refspec, commit=commit)
        #     new_commits.append(new_commit)
        #
        # update_commits_queryset = Commit.objects.filter(project=repository.project, sha__in=db_exist_commits)
        #
        # through_model = Commit.branches.through
        # through_model.objects.bulk_create([
        #     through_model(commit_id=id, branch_id=branch.id)
        #     for id in update_commits_queryset.exclude(branches__id=branch.id).values_list('id', flat=True)
        # ])

    return new_commits


def create_commit(project=None, repository=None, branch=None, refspec=None, commit=None, is_parent=False):

    defaults = {
        'repo_id': commit.hexsha,
        'display_id': commit.hexsha[:7],
        'author': {
            'email': commit.author.email,
            'name': commit.author.name,
            'date': datetime.fromtimestamp(commit.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'committer': {
            'email': commit.committer.email,
            'name': commit.committer.name,
            'date': datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'message': commit.message[:255],
        'stats': {
            'deletions': commit.stats.total.get('deletions', 0),
            'additions': commit.stats.total.get('insertions', 0),
            'total': commit.stats.total.get('lines', 0)
        },
        'timestamp': datetime.fromtimestamp(commit.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'url': repository.url_commit(commit.hexsha)
    }

    new_commit, created = Commit.objects.get_or_create(
        project=project,
        sha=commit.hexsha,
        defaults=defaults
    )
    if not branch:
        branch, _ = Branch.objects.get_or_create(project=repository.project, name=refspec)

    area_default = Area.get_default(project=project)
    area_through_model = Commit.areas.through
    area_through_model.objects.update_or_create(commit_id=new_commit.id, area_id=area_default.id)

    branch_through_model = Commit.branches.through
    branch_through_model.objects.update_or_create(commit_id=new_commit.id, branch_id=branch.id)

    if is_parent:
        return new_commit

    index_number = 0
    for parent in commit.parents:
        index_number += 1

        parent_defaults = {
            'repo_id': parent.hexsha,
            'display_id': parent.hexsha[:7],
            'author': {
                'email': parent.author.email,
                'name': parent.author.name,
                'date': datetime.fromtimestamp(parent.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
            'committer': {
                'email': parent.committer.email,
                'name': parent.committer.name,
                'date': datetime.fromtimestamp(parent.committed_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
            'message': parent.message[:255],
            'stats': {
                'deletions': parent.stats.total.get('deletions', 0),
                'additions': parent.stats.total.get('insertions', 0),
                'total': parent.stats.total.get('lines', 0)
            },
            'timestamp': datetime.fromtimestamp(parent.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'url': repository.url_commit(parent.hexsha)
        }

        parent_commit, parent_created = Commit.objects.get_or_create(
            project=project,
            sha=parent.hexsha,
            defaults=parent_defaults
        )

        area_through_model = Commit.areas.through
        area_through_model.objects.update_or_create(commit_id=parent_commit.id, area_id=area_default.id)

        branch_through_model = Commit.branches.through
        branch_through_model.objects.update_or_create(commit_id=parent_commit.id, branch_id=branch.id)

    return new_commit, created


def create_or_update_commit(project=None, repository=None, branch=None, refspec=None, commit=None, is_parent=False):

    stats = {
        'deletions': commit.stats.total.get('deletions', 0),
        'additions': commit.stats.total.get('insertions', 0),
        'total': commit.stats.total.get('lines', 0)
    }

    defaults = {
        'repo_id': commit.hexsha,
        'display_id': commit.hexsha[:7],
        'author': {
            'email': commit.author.email,
            'name': commit.author.name,
            'date': datetime.fromtimestamp(commit.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'committer': {
            'email': commit.committer.email,
            'name': commit.committer.name,
            'date': datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'message': commit.message[:255],
        'stats': stats,
        'timestamp': datetime.fromtimestamp(commit.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'url': repository.url_commit(commit.hexsha)
    }

    new_commit, created = Commit.objects.get_or_create(
        project=project,
        sha=commit.hexsha,
        defaults=defaults
    )

    if not created:
        new_commit.stats = stats
        new_commit.save()

    if not branch:
        branch, _ = Branch.objects.get_or_create(project=repository.project, name=refspec)

    area_default = Area.get_default(project=project)
    area_through_model = Commit.areas.through
    area_through_model.objects.update_or_create(commit_id=new_commit.id, area_id=area_default.id)

    branch_through_model = Commit.branches.through
    branch_through_model.objects.update_or_create(commit_id=new_commit.id, branch_id=branch.id)

    if is_parent:
        return new_commit

    index_number = 0
    for parent in commit.parents:
        index_number += 1

        parent_defaults = {
            'repo_id': parent.hexsha,
            'display_id': parent.hexsha[:7],
            'author': {
                'email': parent.author.email,
                'name': parent.author.name,
                'date': datetime.fromtimestamp(parent.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
            'committer': {
                'email': parent.committer.email,
                'name': parent.committer.name,
                'date': datetime.fromtimestamp(parent.committed_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
            'message': parent.message[:255],
            'stats': {
                'deletions': parent.stats.total.get('deletions', 0),
                'additions': parent.stats.total.get('insertions', 0),
                'total': parent.stats.total.get('lines', 0)
            },
            'timestamp': datetime.fromtimestamp(parent.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'url': repository.url_commit(parent.hexsha)
        }

        parent_commit, parent_created = Commit.objects.get_or_create(
            project=project,
            sha=parent.hexsha,
            defaults=parent_defaults
        )

        area_through_model = Commit.areas.through
        area_through_model.objects.update_or_create(commit_id=parent_commit.id, area_id=area_default.id)

        branch_through_model = Commit.branches.through
        branch_through_model.objects.update_or_create(commit_id=parent_commit.id, branch_id=branch.id)

    return new_commit, created


def processing_files(project=None, repository=None, ref=None, before=None, after=None, since_time=None):

    repo = repository.get_repo(ref=ref, before=before, after=after)

    if project is None:
        project = repository.project

    refs = []
    if ref is None:
        refs = repository.get_refs()
    else:
        refs = [ref, ]

    commits_changed_files = []

    for refspec in refs:

        try:
            commits = repository.get_commits(ref=ref, before=before, after=after, refspec=refspec)
        except GitCommandError:
            continue

        if since_time:
            commits = filter(
                lambda commit:
                commit.committed_datetime.date() > (datetime.now() - timedelta(days=since_time)).date(),
                commits
            )

        for commit in commits:
            changed_files, result = create_commit_changed_files(project=repository.project, repository=repository,
                                                                repo=repo, refspec=refspec, commit=commit)
            if result:
                commits_changed_files.extend(changed_files)

    return commits_changed_files


def create_commit_changed_files(project=None, repository=None, repo=None, refspec=None, commit=None):

    changed_files = []

    try:
        db_commit = Commit.objects.get(project=project, sha=commit.hexsha)
    except Commit.DoesNotExist:
        return changed_files, False

    parents = list(commit.parents)

    if not commit.parents:
        parents.append(repo.tree('4b825dc642cb6eb9a060e54bf8d69288fbee4904'))

    for parent in parents:

        diffs = {}

        for diff in parent.diff(commit.hexsha, create_patch=True):
            path = diff.a_path
            diff_type = get_diff_type(diff)

            if diff_type in ['A', 'M', 'R']:
                path = diff.b_path

            diffs[path] = diff

        for obj_path, stats in commit.stats.files.items():

            obj_path = prepare_path(obj_path)

            diff = diffs.get(obj_path)

            if diff is None:
                continue

            if diff.a_blob:
                file_sha = diff.a_blob.hexsha

            elif diff.b_blob and get_diff_type(diff) in ['A', 'M', 'R']:
                file_sha = diff.b_blob.hexsha
            else:
                file_sha = str()

            filename = obj_path
            project_file = File.add_file_tree(project, filename, sha=file_sha)

            previous_filename = diff.rename_from

            if previous_filename is None:
                previous_filename = str()

            patch = diff.diff

            status_choice = {
                'A': FileChange.STATUS_ADDED,
                'M': FileChange.STATUS_MODIFIED,
                'D': FileChange.STATUS_DELETED,
                'R': FileChange.STATUS_RENAMED,
                'T': FileChange.STATUS_MODIFIED,
            }
            current_diff_type = get_diff_type(diff)

            # try:
            #     patch = unicode(patch, encoding='utf-8')
            # except UnicodeDecodeError:
            #     patch = ''

            project_file.add_changes(
                commit=db_commit,
                additions=stats.get('insertions'),
                deletions=stats.get('deletions'),
                changes=stats.get('lines'),
                status=status_choice.get(current_diff_type),
                patch=patch,
                previous_filename=previous_filename,
            )

            changed_files.append(project_file.full_filename)

            filename_areas = Area.get_by_filename(project=project, filename=filename)
            code_areas = Area.create_from_code(project=project, filename=filename, patch=patch)

            project_file.areas.add(*filename_areas)
            project_file.areas.add(*code_areas)

            db_commit.areas.add(*filename_areas)
            db_commit.areas.add(*code_areas)
            # Default areas included in results

    return changed_files, True


def processing_rework(project=None, repository=None, ref=None, before=None, after=None, since_time=None):

    repo = repository.get_repo(ref=ref, before=before, after=after)

    if project is None:
        project = repository.project

    refs = []
    if ref is None:
        refs = repository.get_refs()
    else:
        refs = [ref, ]

    for refspec in refs:

        try:
            commits = repository.get_commits(ref=ref, before=before, after=after, refspec=refspec)
        except GitCommandError:
            continue

        if since_time:
            commits = filter(
                lambda commit:
                commit.committed_datetime.date() > (datetime.now() - timedelta(days=since_time)).date(),
                commits
            )

        # for commit in commits:
        #     result = calculate_rework(project=project, repository=repository, repo=repo, refspec=refspec, commit=commit)

    return None


def calculate_rework(project=None, repository=None, repo=None, refspec=None, commit=None):
    try:
        db_commit = Commit.objects.get(project=project, sha=commit.hexsha)
    except Commit.DoesNotExist:
        return False

    max_lines = 0.0
    rework_lines = 0.0

    commit_files_changes = db_commit.filechange_set.filter(
        status=FileChange.STATUS_MODIFIED
    ).annotate(
        full_filename=models.F('file__full_filename')
    )

    for files_changes in commit_files_changes:
        blames = repo.blame_incremental(commit.hexsha, files_changes.full_filename)
        blame_entries = list([blame for blame in blames])

        for blame in blame_entries:

            max_lines += 1

            if blame.commit.author.name != commit.author.name:
                continue

            blame_date = blame.commit.committed_datetime
            commit_date_delta = commit.committed_datetime - timedelta(days=14)

            if blame_date > commit_date_delta:
                rework_lines += 1
    if max_lines:
        db_commit.rework = int((rework_lines / max_lines) * 100)
    db_commit.save()
    return True

