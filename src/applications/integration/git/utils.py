# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
from datetime import datetime, timedelta
import os
import pexpect
from time import sleep
from shutil import rmtree
import hmac
import json
import pytz
import re
import socket
from django.conf import settings
from django.template import Template, Context
from django.http import HttpResponseForbidden, HttpResponseServerError, HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes
from hashlib import sha1
from paramiko import *

from applications.integration.utils import patch_re, output_re
from applications.vcs.models import File, Commit, Branch, FileChange, Area


# from applications.vcs.utils.bugspots import get_code_hotspots

def git_process():
    pass

def perform_execution(repository, command):

    child = pexpect.spawn(command, maxread=8192, timeout=180, cwd=repository.repo_path)

    expect_list = ['Are you sure you want to continue connecting', '(?i)password:', pexpect.EOF]
    i = child.expect(expect_list)

    if i == 0:
        # print('Inside continue')
        child.sendline('yes')
        i = child.expect(expect_list, timeout=30)
    if i == 1:
        # print('Inside password')
        child.sendline(repository.password)
        i = child.expect(expect_list, timeout=None)
    if i == 2:
        # print('Inside EOF block')
        if child.isalive():
            child.close()

    output_lines = child.before
    # print('exitstatus: {}'.format(child.exitstatus))
    have_error = 'fatal' in output_lines
    if child.exitstatus or have_error:
        if child.status > 0 and have_error:
            # output_lines_list = output_lines.split('\r\n')
            # for line in output_lines_list:
            #     print(line)
            raise RuntimeError(output_lines)

    return True


def test_connection(host, user, password=None, port=None):
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    port = int(port) if port else 22
    try:
        client.connect(hostname=host, username=user, password=password, port=port)

        return True, 'Successful connection'
    except SSHException as e:
        return False, e.message
    except socket.error as e:
        return False, e.strerror


def install_hook(host, login, password, port, path, hook, force):
    try:
        transport = Transport((host, int(port)))
        transport.connect(username=login, password=password)
    except SSHException as e:
        return False, e.message

    sftp_client = SFTPClient.from_transport(transport)
    receive = '''#!/bin/bash\npython ./hooks/hook.py'''

    try:
        if not path:
            path = '.'
        if os.path.split(path)[1] != '.git':
            if exists(sftp_client, path=os.path.join(path, '.git')):
                path = os.path.join(path, '.git')

        path = sftp_client.normalize(path=os.path.join(path, 'hooks'))
        if not exists(sftp_client, path=os.path.join(path, 'post-receive')) and not exists(
                sftp_client, path=os.path.join(path, 'hook.py')):

            file_hook = sftp_client.file(os.path.join(path, 'hook.py'), 'w+')
            file_receive_hook = sftp_client.file(os.path.join(path, 'post-receive'), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            sftp_client.chmod(os.path.join(path, 'post-receive'), 0o0300)
            sftp_client.chmod(os.path.join(path, 'hook.py'), 0o0300)

            return True, 'Successful install'
        elif not exists(sftp_client, path=os.path.join(path, 'hook.py')) and exists(
                sftp_client, path=os.path.join(path, 'post-receive')):
            file_hook = sftp_client.file(os.path.join(path, 'hook.py'), 'w+')
            file_receive_hook = sftp_client.file(os.path.join(path, 'post-receive.draft'), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            sftp_client.chmod(os.path.join(path, 'post-receive'), 0o0300)
            sftp_client.chmod(os.path.join(path, 'hook.py'), 0o0300)

            return False, 'Contact the administrator'
        elif exists(sftp_client, path=os.path.join(path, 'post-receive')) and exists(
                sftp_client, path=os.path.join(path, 'hook.py')) and force:

            file_hook = sftp_client.file(os.path.join(path, 'hook.py'), 'w+')
            file_receive_hook = sftp_client.file(os.path.join(path, 'post-receive'), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            sftp_client.chmod(os.path.join(path, 'post-receive'), 0o0300)
            sftp_client.chmod(os.path.join(path, 'hook.py'), 0o0300)

            return True, 'Successful install'
        elif exists(sftp_client, path=os.path.join(path, 'post-receive')) and exists(
                sftp_client, path=os.path.join(path, 'hook.py')) and not force:

            sftp_client.chmod(os.path.join(path, 'post-receive'), 0o0300)
            sftp_client.chmod(os.path.join(path, 'hook.py'), 0o0300)

            return True, 'Successful install'

    except IOError as e:
        return False, e


def exists(sftp, path):
    try:
        sftp.stat(path)
    except IOError as e:
        if e[0] == 2:
            return False
        raise
    else:
        return True


def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    os.chmod(path, mode)


def verify_secret_hook(request):
    header_signature = request.META.get('HTTP_X_HUB_SIGNATURE')
    if header_signature is None:
        return False, HttpResponseForbidden('Permission denied')

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha1':
        return False, HttpResponseServerError('Operation not supported', status=501)

    mac = hmac.new(force_bytes(settings.SECRET_KEYS.get('LOCAL')), msg=force_bytes(request.body), digestmod=sha1)
    if not hmac.compare_digest(force_bytes(mac.hexdigest()), force_bytes(signature)):
        return False, HttpResponseForbidden('Permission denied')

    return True, HttpResponse(status=204)


def sync_full_commits(repository_credential, data=None):
    if data is None:
        data = {}
    host = repository_credential.host
    login = repository_credential.login
    password = repository_credential.password
    port = repository_credential.port
    path = repository_credential.path
    project = repository_credential.project
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    port = int(port) if port else 22
    new_hashes = []
    try:
        client.connect(hostname=host, username=login, password=password, port=port)
        _, stdout_b, _ = client.exec_command(str('cd {}; git show-branch'.format(path)))
        branch_re = re.compile(r'.*\[(?P<branch>(\S+))\]')
        diff_tree_re = re.compile(
            "^:(?P<src_mode>[0-9]{6}) (?P<dst_mode>[0-9]{6}) (?P<src_hash>[0-9a-f]{7,40}) (?P<dst_hash>[0-9a-f]{7,40}) "
            "(?P<status>[ADMRT]|[CR][0-9]{1,3})\s+", re.MULTILINE)
        diff_re_a = re.compile(".+ (?P<status>[ADM]|[R][0-9]{1,3})\s+(?P<file1>.+)", re.MULTILINE)
        diff_re_d = re.compile(".+ (?P<status>[ADM]|[R][0-9]{1,3})\s+(?P<file1>.+)", re.MULTILINE)
        diff_re_m = re.compile(".+ (?P<status>[ADM]|[R][0-9]{1,3})\s+(?P<file1>.+)", re.MULTILINE)
        diff_re_r1 = re.compile('.+ (?P<status>[ADM]|[R][0-9]{1,3}).+\t(?P<file2>.+)$', re.MULTILINE)
        diff_re_r2 = re.compile('.+ (?P<status>[ADM]|[R][0-9]{1,3})\s(?P<file1>.+)\t\S+$', re.MULTILINE)

        for line in stdout_b.readlines():
            branch = branch_re.match(line)
            if not branch:
                continue
            branch = branch.groupdict().get('branch')
            branch_obj, created = Branch.objects.get_or_create(project=project, name=branch)

            format_string = '{"sha": "%H"}'
            _, stdout, _ = client.exec_command(
                str("cd {}; git log {} --pretty=format:'{}'".format(path, branch, format_string, branch)))
            commits = [json.loads(x.decode('unicode-escape'), strict=False) for x in stdout.readlines()]
            for commit in commits[::-1]:
                try:
                    commit_obj = Commit.objects.get(project=project, sha=commit.get('sha'))
                    commit_obj.branches.add(branch_obj)
                    continue
                except Commit.MultipleObjectsReturned:
                    continue
                except Commit.DoesNotExist:
                    pass

                props = {'added': [],
                         'removed': [],
                         'modified': [],
                         'files': {}
                         }
                format_string = '{"author": {"name": "%an", "email": "%ae", "date": "%aI"},' \
                                ' "committer": {"name": "%cn", "email": "%ce", "date": "%cI"}, "message": "%s",' \
                                ' "tree": {"sha": "%T"}, "parents": "%P", "sha": "%H"}\n'

                _, output, _ = client.exec_command(
                    "cd {}; git show --format=format:'{}' {}".format(path, format_string, commit.get('sha')))
                output = output.read().split('\n\n')
                commit = json.loads(output[0].decode('unicode-escape'), strict=False)
                parents = commit.get('parents').split(' ') if commit.get('parents') else []
                commit['parents'] = [{'sha': sha} for sha in parents]
                props.update(commit)
                if not parents:
                    _, output_diff_stats, _ = client.exec_command(
                        "cd {}; git show --numstat {} --format=''".format(path, commit.get('sha')))
                    output_diff_stats = output_diff_stats.readlines()  # .split('\\n')
                    output_diff = output[1].split('diff --git')[1:]
                    if len(output_diff) == len(output_diff_stats):
                        for i in range(0, len(output_diff)):
                            file_diff_stats = output_diff_stats[i].split('\t')
                            file_diff = output_diff[i][output_diff[i].find('@'):]
                            commit_file = {
                                'filename': file_diff_stats[2].strip(),
                                'additions': file_diff_stats[0],
                                'deletions': file_diff_stats[1],
                                'patch': file_diff
                            }
                            props['files'][commit_file['filename']] = commit_file
                else:
                    for parent in parents:
                        _, output_diff_stats, _ = client.exec_command(
                            'cd {}; git diff --numstat {} {}'.format(path, parent, props.get('sha')))

                        output_diff_stats = output_diff_stats.readlines()
                        output_diff = output[1].split('diff --git')[1:]

                        if len(output_diff) == len(output_diff_stats):
                            for i in range(0, len(output_diff)):
                                file_diff_stats = output_diff_stats[i].split('\t')
                                file_diff = output_diff[i][output_diff[i].find('@'):]
                                full_path = ''
                                if '{' in file_diff_stats[2]:
                                    temp_var = file_diff_stats[2].split('{')
                                    full_path = temp_var[0]
                                    file_diff_stats[2] = temp_var[1].replace('}', '').strip()
                                if '=>' in file_diff_stats[2]:
                                    file_diff_stats[2] = file_diff_stats[2].split('=>')[1]
                                commit_file = {
                                    'filename': full_path + file_diff_stats[2].strip(),
                                    'additions': file_diff_stats[0],
                                    'deletions': file_diff_stats[1],
                                    'patch': file_diff.strip()
                                }
                                props['files'][commit_file['filename']] = commit_file

                _, output, _ = client.exec_command(
                    'cd {}; git diff-tree -r -C {} --no-commit-id'.format(path, props.get('sha')))

                output = output.read()
                if not output and output_diff:
                    _, output, _ = client.exec_command('cd {}; git hash-object -t tree /dev/null'.format(path))
                    output_null_hash = output.read().strip()
                    _, output, _ = client.exec_command(
                        'cd {}; git diff-tree -r -C {} {} --no-commit-id'.format(path, output_null_hash,
                                                                                 props.get('sha')))
                    output = output.read()

                output = output.split('\n')[:-1]

                for line in output:
                    i = diff_tree_re.match(line)
                    item = i.groupdict()
                    try:
                        if item['status'] == 'A':  # addition of a file
                            item_file = diff_re_a.match(line).groupdict()
                            props['added'].append(item_file['file1'])
                            props['files'][item_file['file1']]['status'] = 'added'
                            props['files'][item_file['file1']]['sha'] = item['dst_hash']
                        elif item['status'] == 'D':  # deletion of a file
                            item_file = diff_re_d.match(line).groupdict()
                            props['removed'].append(item_file['file1'])
                            props['files'][item_file['file1']]['status'] = 'deleted'
                            props['files'][item_file['file1']]['sha'] = item['dst_hash']
                        elif item['status'] == 'M':  # modification of the contents or mode of a file
                            item_file = diff_re_m.match(line).groupdict()
                            props['modified'].append(item_file['file1'])
                            props['files'][item_file['file1']]['status'] = 'modified'
                            props['files'][item_file['file1']]['sha'] = item['dst_hash']
                        elif item['status'][0] == 'R':  # renaming of a file
                            file2 = diff_re_r1.match(line).groupdict()
                            file1 = diff_re_r2.match(line).groupdict()
                            props['removed'].append(file1['file1'])
                            props['added'].append(file2['file2'])
                            props['files'][file2['file2']]['status'] = 'renamed'
                            props['files'][file2['file2']]['previous_filename'] = file1['file1']
                            props['files'][file2['file2']]['sha'] = item['dst_hash']
                        else:
                            pass
                    except KeyError:
                        pass
                props['files'] = [val for _, val in props['files'].items()]
                new_commit = create_commit(props, repository_credential, branch_obj, project.organization_id)
                new_hashes.append(new_commit.sha)

        return new_hashes
    except SSHException as e:
        print(False, e)
    except socket.error as e:
        print(False, e)
    except Exception as e:
        print(False, e)


def create_commit(commit_json, repository, branch, organization_id):
    sha_commit = commit_json.get('sha')
    commit, created = Commit.objects.get_or_create(sha=sha_commit, project=repository.project)
    total_number_of_changed = 0
    number_of_chunks = 0
    max_lines = 0.0
    rework_lines = 0.0
    list_directories = list()

    commit.project = repository.project
    commit.repo_id = sha_commit
    commit.sha = sha_commit
    commit.display_id = sha_commit[:7]
    commit.author = commit_json.get('author')
    commit.committer = commit_json.get('committer')
    commit.message = commit_json.get('message')[:255]
    commit.url = ''
    commit.timestamp = commit_json.get('author', None).get('date') if commit_json.get('author',
                                                                                      None) else None
    if commit.timestamp is None:
        commit.timestamp = commit_json.get('commiter', None).get('date') if commit_json.get('commiter',
                                                                                            None) else None

    commit.save()

    commit.branches.add(branch)

    index_number = 0
    for parent in commit_json.get('parents'):
        index_number += 1
        parent_commit_sha = parent.get('sha')

        parent_commit, created = Commit.objects.get_or_create(project=repository.project, sha=parent_commit_sha)
        parent_commit.branches.add(branch)
        commit.add_parent(parent_commit, index_number)

    for commit_file in commit_json.get('files'):
        created = False
        sha = commit_file.get('sha')
        filename = commit_file.get('filename')
        filename_list = filename.split('/')
        parent = None
        for name in filename_list:
            project_file, created = File.objects.get_or_create(project=repository.project, filename=name,
                                                               parent=parent)
            parent = project_file

        previous_filename = commit_file.get('previous_filename', str())

        if created or previous_filename:
            project_file.sha = sha
            project_file.save()

        additions = commit_file.get('additions')
        deletions = commit_file.get('deletions')
        changes = int(additions) + int(deletions)

        status = commit_file.get('status', '')

        patch = commit_file.get('patch', '')

        total_number_of_changed += changes
        number_of_chunks += len(patch_re.findall(patch))
        list_directories.append('/'.join(filename.split('/')[:-1]))

        status_choice = {
            'added': FileChange.STATUS_ADDED,
            'modified': FileChange.STATUS_MODIFIED,
            'deleted': FileChange.STATUS_DELETED,
            'renamed': FileChange.STATUS_RENAMED,
            'removed': FileChange.STATUS_DELETED,
        }

        project_file.add_changes(
            commit=commit,
            additions=additions,
            deletions=deletions,
            changes=changes,
            status=status_choice.get(status),
            patch=patch,
            previous_filename=previous_filename,
        )

        for area in filename.split('/')[1::-1]:
            try:
                file_area = Area.objects.get(project=repository.project, name=area)
                project_file.areas.add(file_area)
                commit.areas.add(file_area)
            except Area.DoesNotExist:
                continue
        area = Area.get_default(project=commit.project)
        project_file.areas.add(area)
        commit.areas.add(area)

        if status_choice.get(status) != FileChange.STATUS_MODIFIED:
            continue
        for i in patch_re.finditer(patch):
            item = i.groupdict()
            end_new = int(item.get('end_orig')) + int(item.get('start_orig')) - 1
            if end_new == -1:
                continue
            output_git = git_process(['blame', '{}^'.format(commit.sha), '-L',
                                      '{},{}'.format(item.get('start_orig'), str(end_new)),
                                      filename, '-w'], commit.project_id, organization_id)
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
                    date_delta = parse_datetime(commit.timestamp) - timedelta(days=14)
                    if date > date_delta:
                        rework_lines += 1
    number_of_files = len(commit_json.get('files'))
    number_of_directories = len(set(list_directories))

    commit.output = total_number_of_changed * (
            (number_of_chunks * 0.5) + (number_of_files - 1) + ((number_of_directories - 1) * 2)) * 2
    if max_lines:
        commit.rework = (rework_lines / max_lines) * 100

    commit.save()

    return commit


web_hook = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json
import re
import subprocess
import sys

from collections import OrderedDict
from datetime import datetime

try:
    from urllib2 import urlopen as urlopen
    from urllib2 import Request as Request
except ImportError:
    from urllib.request import urlopen as urlopen
    from urllib.request import Request as Request


def git(args):
    args = ['git'] + args
    git_process = subprocess.Popen(args, stdout=subprocess.PIPE)
    details = git_process.stdout.read()
    details = details.decode("utf-8").strip()
    return details


def _git_config():
    raw_config = git(['config', '-l', '-z'])
    items = raw_config.split("\\0")
    items = filter(lambda i: len(i) > 0, items)
    items = [item.partition("\\n")[0:3:2] for item in items]
    return OrderedDict(items)


GIT_CONFIG = _git_config()


def get_config(key, default=None):
    return GIT_CONFIG.get(key, default)


POST_URL = '{{ domain }}'
POST_SECRET_TOKEN = '{{ secret_key }}'
REPO_USERNAME = '{{ custom_user }}'
REPO_NAME = '{{ repos_name }}'


def get_revisions(old_sha, new_sha, head_commit=False):
    if re.match("^0+$", old_sha):
        if not head_commit:
            return []

        commit_range = '%s~1..%s' % (new_sha, new_sha)
    else:
        commit_range = '%s..%s' % (old_sha, new_sha)

    revs = git(['rev-list', '--pretty=medium', '--reverse', commit_range])
    sections = revs.split('\\n\\n')

    revisions = []
    s = 0
    while s < len(sections):
        lines = sections[s].split('\\n')

        props = {'sha': lines[0].strip().split(' ')[1],
                 'added': [],
                 'removed': [],
                 'modified': [],
                 'files': {}
                 }

        format_string = '{"author": {"name": "%an", "email": "%ae"},' \\
                        ' "committer": {"name": "%cn", "email": "%ce"}, "message": "%s",' \\
                        ' "tree": {"sha": "%T"}, "parents": "%P"}\\n'

        output = git(['show',
                      '--format=format:{}'.format(format_string),
                      '{}'.format(props['sha'])]).split('\\n\\n')

        commit = json.loads(output[0])
        parents = commit.get('parents').split(' ')
        commit['parents'] = [{'sha': sha} for sha in parents]
        props.update(commit)
        for parent in parents:
            output_diff_stats = git(
                ['diff', '--numstat', '{}'.format(parent), '{}'.format(props.get('sha'))]).split('\\n')
            output_diff = output[1].split('diff --git')[1:]
            if len(output_diff) == len(output_diff_stats):
                for i in range(0, len(output_diff)):
                    file_diff_stats = output_diff_stats[i].split('\\t')
                    file_diff = output_diff[i][output_diff[i].find('@'):]
                    commit_file = {
                        'filename': file_diff_stats[2],
                        'additions': file_diff_stats[0],
                        'deletions': file_diff_stats[1],
                        'patch': file_diff
                    }
                    props['files'][commit_file['filename']] = commit_file

        output = git(['diff-tree', '-r', '-C', '{}'.format(props['sha'])])

        diff_tree_re = re.compile(
            "^:(?P<src_mode>[0-9]{6}) (?P<dst_mode>[0-9]{6}) (?P<src_hash>[0-9a-f]{7,40}) (?P<dst_hash>[0-9a-f]{7,40}) "
            "(?P<status>[ADMTUX]|[CR][0-9]{1,3})\s+(?P<file1>\S+)(?:\s+(?P<file2>\S+))?$", re.MULTILINE)

        for i in diff_tree_re.finditer(output):
            item = i.groupdict()
            if item['status'] == 'A':  # addition of a file
                props['added'].append(item['file1'])
                props['files'][item['file1']]['status'] = 'added'
                props['files'][item['file1']]['sha'] = item['dst_hash']
            elif item['status'][0] == 'C':  # copy of a file into a new one
                props['added'].append(item['file2'])
                props['files'][item['file1']]['status'] = 'added'
                props['files'][item['file1']]['sha'] = item['dst_hash']
            elif item['status'] == 'D':  # deletion of a file
                props['removed'].append(item['file1'])
                props['files'][item['file1']]['status'] = 'deleted'
                props['files'][item['file1']]['sha'] = item['dst_hash']
            elif item['status'] == 'M':  # modification of the contents or mode of a file
                props['modified'].append(item['file1'])
                props['files'][item['file1']]['status'] = 'modified'
                props['files'][item['file1']]['sha'] = item['dst_hash']
            elif item['status'][0] == 'R':  # renaming of a file
                props['removed'].append(item['file1'])
                props['added'].append(item['file2'])
                props['files'][item['file2']]['status'] = 'renamed'
                props['files'][item['file2']]['previous_filename'] = item['file1']
                props['files'][item['file2']]['sha'] = item['dst_hash']
            elif item['status'] == 'T':  # change in the type of the file
                props['modified'].append(item['file1'])
                props['files'][item['file2']]['status'] = ''
                props['files'][item['file1']]['sha'] = item['dst_hash']
            else:
                pass

        props['files'] = [val for _, val in props['files'].items()]

        key, val = lines[2].split(' ', 1)
        props[key[:-1].lower()] = val.strip()

        basetime = datetime.strptime(props['date'][:-6], "%a %b %d %H:%M:%S %Y")
        tzstr = props['date'][-5:]
        props['date'] = basetime.strftime('%Y-%m-%dT%H:%M:%S') + tzstr

        if head_commit:
            return props

        revisions.append(props)
        s += 2

    return revisions


def get_base_ref(commit, refer):
    branches = git(['branch', '--contains', commit]).split('\\n')
    curr_branch_re = re.compile('^\* \w+$')
    curr_branch = None

    if len(branches) > 1:
        on_master = False
        for branch in branches:
            if curr_branch_re.match(branch):
                curr_branch = branch.strip('* \\n')
            elif branch.strip() == 'master':
                on_master = True

        if curr_branch is None and on_master:
            curr_branch = 'master'

    if curr_branch is None:
        curr_branch = branches[0].strip('* \\n')

    base_ref = 'refs/heads/%s' % curr_branch

    if base_ref == refer:
        return None
    else:
        return base_ref


def make_json(old_sha, new_sha, refer):
    data_commit = {
        'before': old_sha,
        'after': new_sha,
        'ref': refer,
        'ref_type': 'commit',
        'repository': {
            'full_name': '{}/{}'.format(REPO_USERNAME, REPO_NAME),
            'name': REPO_NAME,
        },
        'commits': []
    }

    revisions = get_revisions(old_sha, new_sha)
    data_commit['commits'] = [r for r in revisions]
    data_commit['size'] = len(data_commit.get('commits'))
    data_commit['head_commit'] = get_revisions(old_sha, new_sha, True)

    base_ref = get_base_ref(new_sha, refer)
    if base_ref:
        data_commit['base_ref'] = base_ref

    post(POST_URL, json.dumps(data_commit), 'push')

    return True


def make_json_tags(old, new_sha, ref):
    format_string = '{"tagger": {"username": "%(taggername)", "email": "%(taggeremail)"}}'
    tagger = git(['for-each-ref', '--format={}'.format(format_string), ref])
    ref = ref.split('/')

    data_commit = {
        'ref': '/'.join(ref[2:]),
        'ref_type': 'tag',
        'sha': new_sha,
        'repository': {
            'full_name': '{}/{}'.format(REPO_USERNAME, REPO_NAME),
            'name': REPO_NAME,
        }
    }
    data_commit.update(json.loads(tagger))

    post(POST_URL, json.dumps(data_commit), 'create')
    return True


def make_json_delete(old, new, ref):
    ref_type = ref.split('/')[1]
    data_commit = {
        'ref': '/'.join(ref.split('/')[2:]),
        'ref_type': ref_type,
        'repository': {
            'full_name': '{}/{}'.format(REPO_USERNAME, REPO_NAME),
            'name': REPO_NAME,
        }
    }

    post(POST_URL, json.dumps(data_commit), 'delete')

    return True


def post(url, data_commit, event):
    headers = {
        'Content-Type': 'application/json',
        'X-Git-Event': event,
    }

    if POST_SECRET_TOKEN is not None:
        import hmac
        import hashlib
        if isinstance(data_commit, str):
            mac = hmac.new(POST_SECRET_TOKEN.encode('utf-8'), msg=data_commit.encode('utf-8'), digestmod=hashlib.sha1)
        else:
            mac = hmac.new(POST_SECRET_TOKEN.encode('utf-8'), msg=data_commit, digestmod=hashlib.sha1)
        signature = 'sha1=' + mac.hexdigest()
        headers['X-Hub-Signature'] = signature

    if isinstance(data_commit, str):
        request = Request(url=url, data=data_commit.encode('utf-8'), headers=headers)
    else:
        request = Request(url=url, data=data_commit, headers=headers)
    urlopen(request)


if __name__ == '__main__':
    for line in sys.stdin:
        old, new, ref = line.strip().split(' ')
        if 'tag' in ref and not re.match("^0+$", new):
            make_json_tags(old, new, ref)

        if re.match("^0+$", new):
            make_json_delete(old, new, ref)

        if 'heads' in ref and not re.match("^0+$", new) and not re.match("^0+$", old):
            make_json(old, new, ref)
'''


def generate_hook(domain, username, repos_name, project_id):
    domain = '{}/api/git/hook/{}/'.format(domain, project_id)
    template_hook = Template(web_hook)
    context_dict = {
        'domain': domain,
        'custom_user': username,
        'repos_name': repos_name,
        'secret_key': settings.SECRET_KEYS.get('LOCAL')
    }
    return template_hook.render(Context(context_dict))
