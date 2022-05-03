# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta

import hmac
import json

import paramiko as paramiko
import pytz
import re
import socket
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError, HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes
from hashlib import sha1
from paramiko import *

from applications.integration.utils import patch_re, output_re, git_process
from applications.vcs.models import File, Commit, Branch, FileChange, Area


# from applications.vcs.utils.bugspots import get_code_hotspots


def test_connection(host, user, password=None, port=None):
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    port = int(port) if port else 22
    try:
        client.connect(hostname=host, username=user, password=password, port=port)

        return True, 'Successful connection'
    except SSHException as e:
        return False, e
    except socket.error as e:
        return False, e


def install_hook(host, login, password, port, path, hook, force):
    try:
        transport = Transport((host, int(port)))
        transport.connect(username=login, password=password)
    except SSHException as e:
        return False, e

    sftp_client = SFTPClient.from_transport(transport)
    receive = '''#!/bin/bash\npython ./hooks/hook.py'''

    try:
        if not path:
            path = '.'
        path = sftp_client.normalize(path=path + '/hooks')
        if not exists(sftp_client, path=path + '/post-receive') and not exists(sftp_client, path=path + '/hook.py'):
            file_hook = sftp_client.file('{}/hook.py'.format(path), 'w+')
            file_receive_hook = sftp_client.file('{}/post-receive'.format(path), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            return True, 'Successful install'
        elif not exists(sftp_client, path=path + '/hook.py') and exists(sftp_client, path=path + '/post-receive'):
            file_hook = sftp_client.file('{}/hook.py'.format(path), 'w+')
            file_receive_hook = sftp_client.file('{}/post-receive.draft'.format(path), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            return False, 'Contact the administrator'
        elif exists(sftp_client, path=path + '/post-receive') and exists(sftp_client, path=path + '/hook.py') and force:
            file_hook = sftp_client.file('{}/hook.py'.format(path), 'w+')
            file_receive_hook = sftp_client.file('{}/post-receive'.format(path), 'w+')

            if file_hook.writable() and file_receive_hook.writable():
                file_hook.write(hook)
                file_receive_hook.write(receive)
            else:
                return False, 'File not writable'

            file_hook.close()
            file_receive_hook.close()

            return True, 'Successful install'
        elif exists(sftp_client, path=path + '/post-receive') and exists(sftp_client,
                                                                         path=path + '/hook.py') and not force:
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


def sync_full_commits(repository_credential):
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


