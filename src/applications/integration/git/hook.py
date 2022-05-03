# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.conf import settings
from django.template import Template, Context

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
