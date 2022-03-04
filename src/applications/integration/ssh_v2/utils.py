# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta

import hmac
import json
import pytz
import re
import socket
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError, HttpResponse
from django.utils import dateparse, timezone
from dateutil import parser as datetimeparser

from django.utils.encoding import force_bytes
from hashlib import sha1, md5
from django.db import models
from applications.project.models import Project
from applications.vcs.models import File, Commit, Branch, FileChange, Area


patch_re = re.compile(
    '^@@ -(?P<start_orig>[0-9]+),(?P<end_orig>[0-9]+) \+(?P<start_new>[0-9]+),(?P<end_new>[0-9]+) @@',
    re.MULTILINE)

output_re = re.compile(
    '^.+ \((?P<author_name>.*) (?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}) (?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2}) .(?P<tz>[0-9]{4}) (?P<lines>.*)\) (?P<data>.*)',
    re.MULTILINE)


status_choice = {
    'unknown': FileChange.STATUS_UNKNOWN,
    'added': FileChange.STATUS_ADDED,
    'modified': FileChange.STATUS_MODIFIED,
    'deleted': FileChange.STATUS_DELETED,
    'renamed': FileChange.STATUS_RENAMED,
    'removed': FileChange.STATUS_DELETED,
}


def prepare_branch(project, branch_name):
    ref = branch_name
    if "refs/remotes/origin/" in ref:
        ref = ref[len("refs/remotes/origin/"):]
    elif "remotes/origin/" in ref:
        ref = ref[len("remotes/origin/"):]
    elif "origin/" in ref:
        ref = ref[len("origin/"):]
    elif "refs/heads/" in ref:
        ref = ref[len("refs/heads/"):]
    elif "heads/" in ref:
        ref = ref[len("heads/"):]
    branch, created = Branch.objects.get_or_create(project=project, name=ref)
    return branch


def prepare_commit_sha(commit):
    sha = commit.get('sha', None)
    if not sha:
        commit_files = commit.get('files', [])
        sha = commit_files[0].get('sha', None)
    return sha


def sync_full_commits(project=None, repository=None, data=None):
    new_hashes = []

    commits = data.get('commits', [])
    head_commit = data.get('head_commit', None)

    if head_commit:
        commits.append(head_commit)

    commit_sha_from_commits = map(lambda x: prepare_commit_sha(x), commits)

    exist_commit_sha = list(project.commits.filter(sha__in=commit_sha_from_commits).values_list('sha', flat=True))

    new_commits_sha = filter(lambda x: prepare_commit_sha(x) not in exist_commit_sha, commits)

    for commit in new_commits_sha:
        new_branch_list = list()

        commit["sha"] = prepare_commit_sha(commit)

        if not commit["sha"]:
            continue

        if "branches" in commit:

            commit_branches = commit.get("branches")

            if not commit_branches:
                commit_branches = ["main", ]

            for branch_name in commit_branches:
                try:

                    branch = prepare_branch(project=project, branch_name=branch_name)

                    new_branch_list.append(branch)
                except Exception as e:
                    continue
        else:
            if 'ref' in data:
                if data['ref'] != '':
                    new_branch = prepare_branch(project=project, branch_name=data['ref'])
                    new_branch_list.append(new_branch)

        try:
            commit = Commit.objects.get(project=project, sha=commit["sha"])
            commit.branches.add(*new_branch_list)
        except Commit.DoesNotExist:
            new_commit = create_commit(project=project, repository=repository, commit=commit, branch_list=new_branch_list, is_parent=False)
            new_hashes.append(new_commit.sha)
        except Commit.MultipleObjectsReturned as e:
            continue
        except RuntimeError as e:
            continue
        except TypeError as e:
            continue

    return new_hashes


def create_commit(project=None, repository=None, commit=None, branch_list=None, is_parent=False):
    new_commit_tmpl = Commit()
    sha_commit = commit["sha"]

    new_commit_tmpl.project = project
    new_commit_tmpl.repo_id = repository.id
    new_commit_tmpl.sha = sha_commit
    new_commit_tmpl.display_id = sha_commit[:7]

    new_commit_tmpl.author = commit.get("author", {})
    new_commit_tmpl.committer = commit.get("committer", {})

    commit_message = commit.get("message")
    if commit_message:
        new_commit_tmpl.message = commit_message[:255]
    else:
        new_commit_tmpl.message = "--empty--"

    new_commit_tmpl.stats = commit.get("stats", dict(additions=0, deletions=0, total=0))

    commit_datetime = commit.get("date")

    if dateparse.parse_datetime(commit_datetime) is None:
        try:
            commit_datetime = timezone.datetime.strptime(commit_datetime, '%A, %B %d, %Y %I:%M:%S %p')
            commit_datetime = commit_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        except ValueError:
            commit_datetime = timezone.datetime.strptime(commit_datetime, '%A, %B %d, %Y %I')
            commit_datetime = commit_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            commit_datetime = timezone.now().strftime('%Y-%m-%dT%H:%M:%S')

    new_commit_tmpl.timestamp = commit_datetime
    new_commit_tmpl.url = ''
    # new_commit_tmpl.save()

    new_commit, created = Commit.objects.get_or_create(
        project_id=new_commit_tmpl.project_id,
        sha=new_commit_tmpl.sha,
        defaults={
            'repo_id': new_commit_tmpl.repo_id,
            'display_id': new_commit_tmpl.display_id,
            'author': new_commit_tmpl.author,
            'committer': new_commit_tmpl.committer,
            'message': new_commit_tmpl.message,
            'stats': new_commit_tmpl.stats,
            'timestamp': new_commit_tmpl.timestamp,
            'url': new_commit_tmpl.url
        }

    )

    area_default = Area.get_default(project)
    new_commit.areas.add(area_default)
    new_commit.branches.add(*branch_list)

    if is_parent:  # TODO: FIX Exception RuntimeError: 'maximum recursion depth exceeded while calling a Python object'
        new_commit.areas.add(area_default)
        return new_commit

    index_number = 0
    try:
        for parent in commit.get("parents", list()):
            index_number += 1
            parent_commit_sha = parent["sha"]
            try:
                parent_commit = Commit.objects.get(project_id=repository.project_id, sha=parent_commit_sha)
            except Commit.DoesNotExist:
                parent_commit = create_commit(project=project, repository=repository,
                                              commit=parent, branch_list=branch_list, is_parent=True)
            except Commit.MultipleObjectsReturned:
                continue

            parent_commit.branches.add(*branch_list)
            new_commit.add_parent(parent_commit, index_number)
    except TypeError as e:
        raise TypeError(e.message)

    return new_commit


def processing_commit_file_v2(project=None, repository=None, data=None):
    file_list = list()

    if 'file_tree' in data:
        file_tree_data = data['file_tree']
        if isinstance(file_tree_data, (list, tuple)):
            for file_item in file_tree_data:
                try:
                    project_file = File.add_file_tree(project, file_item)
                    file_list.append(project_file.full_filename)
                except Exception as e:
                    continue

    commits = data.get('commits', [])

    for commit in commits:
        commit["sha"] = prepare_commit_sha(commit)
        new_commit = Commit.objects.filter(project=project, sha=commit["sha"]).last()

        for commit_file in commit.get("files", list()):
            filename = commit_file["filename"]

            project_file = File.add_file_tree(project, filename, sha=commit_file["sha"])

            previous_filename = commit_file["previous_filename"]

            if previous_filename is None:
                previous_filename = str()

            patch = commit_file.get("patch", "")
            blame = commit_file.get("blame", "")
            status = commit_file.get("status") if commit_file.get("status") else "modified"

            project_file.add_changes(
                commit=new_commit,
                additions=commit_file["additions"],
                deletions=commit_file["deletions"],
                changes=commit_file["changes"],
                status=status_choice.get(status),
                patch=patch,
                blame=blame,
                previous_filename=previous_filename,
            )

            file_list.append(project_file.full_filename)

            filename_areas = Area.get_by_filename(project=project, filename=filename)
            code_areas = Area.create_from_code(project=project, filename=filename, patch=patch)
            project_file.areas.add(*filename_areas)
            project_file.areas.add(*code_areas)

            new_commit.areas.add(*filename_areas)
            new_commit.areas.add(*code_areas)
            # Default areas included in results

    file_list = list(set(file_list))
    return file_list


def calculate_rework_one_commit_v2(commit_id):
    try:
        commit = Commit.objects.get(pk=commit_id)
    except (Commit.DoesNotExist, Commit.MultipleObjectsReturned):
        return False

    max_lines = 0.0
    rework_lines = 0.0
    file_changes_in_commit = commit.filechange_set.filter(status=FileChange.STATUS_MODIFIED).annotate(full_filename=models.F('file__full_filename'))
    for file_change_obj in file_changes_in_commit:
        for i in patch_re.finditer(file_change_obj.patch):
            item = i.groupdict()
            end_new = int(item.get('end_orig')) + int(item.get('start_orig')) - 1
            if end_new == -1:
                continue
            output_git = file_change_obj.blame
            if output_git:
                for j in output_re.finditer(output_git):
                    output_item = j.groupdict()
                    if not output_item.get('data'):
                        continue
                    max_lines += 1
                    author_name = output_item.get('author_name')
                    if author_name != commit.author.get('name'):
                        continue
                    date = datetime(year=int(output_item.get('year')), month=int(output_item.get('month')),
                                    day=int(output_item.get('day')), hour=int(output_item.get('hour')),
                                    minute=int(output_item.get('minute')),
                                    second=int(output_item.get('second')),
                                    tzinfo=pytz.UTC)
                    date_delta = commit.timestamp - timedelta(days=14)
                    if date > date_delta:
                        rework_lines += 1
    if max_lines:
        commit.rework = int((rework_lines / max_lines) * 100)
    commit.save()
    return True


def processing_commits_fast(project=None, repository=None, data=None):

    if data is None:
        return False

    if repository is None:
        return False

    if project is None:
        project = repository.project

    ref = data.get('ref', 'master')
    commits = data.get('commits', [])

    branch = prepare_branch(project, ref)

    for commit in commits:
        sha = commit['sha']
        display_id = commit['sha'][:7]
        message = commit['message'][:255]
        timestamp = datetimeparser.parse(commit['date'])
        author = commit['author']
        committer = commit['committer']
        url = ''

        defaults = {
            'repo_id': sha,
            'display_id': display_id,
            'message': message,
            'author': author,
            'committer': committer,
            'stats': {
                'deletions': 0,
                'additions': 0,
                'total': 0
            },
            'timestamp': timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
            'url': url
        }
        new_commit, created = Commit.objects.get_or_create(
            project=project,
            sha=sha,
            defaults=defaults
        )
        area_default = Area.get_default(project=project)
        area_through_model = Commit.areas.through
        area_through_model.objects.update_or_create(commit_id=new_commit.id, area_id=area_default.id)

        branch_through_model = Commit.branches.through
        branch_through_model.objects.update_or_create(commit_id=new_commit.id, branch_id=branch.id)

    return True
