import binascii
import traceback
import warnings
import sys
import argparse
import subprocess
import json
import re
import logging
import os


try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.sessions import Session
    from requests.adapters import Retry
except ImportError:
    warnings.warn("Please install 'requests' library, e.g. 'pip install requests'."\
                  "Then run the command again.")
    sys.exit(1)

# Syntax sugar.
_ver = sys.version_info

#: Python 2.x?
is_py2 = (_ver[0] == 2)

if is_py2:
    raise Exception("Python 2.x is deprecated.")

#: Python 3.x?
is_py3 = (_ver[0] == 3)

#: OS Windows
is_windows = (os.name == 'nt')

#: OS MacOS or Linux
is_posix = (os.name == 'posix')

COMMAND_GET_ALL_COMMITS_SHA = "git log --reflog --pretty=format:%H"
COMMAND_COMMIT = "git show --reverse --first-parent --raw --numstat --abbrev=40 --full-index -p -M --pretty=format:'Commit:\t%H%nDate:\t%ai%nTree:\t%T%nParents:\t%P%nAuthor:\t%an\t%ae\t%ai%nCommitter:\t%cn\t%ce\t%ci%nMessage:\t%s%n' {}"
COMMAND_COMMIT_BRANCH = "git branch --contains {}"

DEBUG = True
COMMIT_COUNT = 10

# PATTERNS
RE_OCTAL_BYTE = re.compile(r"""\\\\([0-9]{3})""")
RE_COMMIT_HEADER = re.compile(
    r"""^Commit:\t(?P<sha>[0-9A-Fa-f]+)\nDate:\t(?P<date>.*)\nTree:\t(?P<tree>[0-9A-Fa-f]+)\nParents:\t(?P<parents>.*)\nAuthor:\t(?P<author>.*)\nCommitter:\t(?P<committer>.*)\nMessage:\t(?P<message>.*)?(?:\n\n|$)?(?P<file_stats>(?:^:.+\n)+)?(?P<file_numstats>(?:.+\t.*\t.*\n)+)?(?:\n|\n\n|$)?(?P<patch>(?:diff[ ]--git(?:.+\n)+)+)?(?:\n\n|$)?""",
    re.VERBOSE | re.MULTILINE)
RE_COMMIT_DIFF = re.compile(
    r"""^diff[ ]--git[ ](?P<a_path_fallback>"?a/.+?"?)[ ](?P<b_path_fallback>"?b/.+?"?)\n(?:^old[ ]mode[ ](?P<old_mode>\d+)\n^new[ ]mode[ ](?P<new_mode>\d+)(?:\n|$))?(?:^similarity[ ]index[ ]\d+%\n^rename[ ]from[ ](?P<rename_from>.*)\n^rename[ ]to[ ](?P<rename_to>.*)(?:\n|$))?(?:^new[ ]file[ ]mode[ ](?P<new_file_mode>.+)(?:\n|$))?(?:^deleted[ ]file[ ]mode[ ](?P<deleted_file_mode>.+)(?:\n|$))?(?:^index[ ](?P<a_blob_id>[0-9A-Fa-f]+)\.\.(?P<b_blob_id>[0-9A-Fa-f]+)[ ]?(?P<b_mode>.+)?(?:\n|$))?(?:^---[ ](?P<a_path>[^\t\n\r\f\v]*)[\t\r\f\v]*(?:\n|$))?(?:^\+\+\+[ ](?P<b_path>[^\t\n\r\f\v]*)[\t\r\f\v]*(?:\n|$))?""",
    re.VERBOSE | re.MULTILINE)


def _octal_repl(match_obj):
    value = match_obj.group(1)
    value = int(value, 8)
    value = chr(value)
    return value


def _decode_path(path, has_ab_prefix=True):
    if path == '/dev/null':
        return None

    if path.startswith('"') and path.endswith('"'):
        path = (path[1:-1].replace('\\n', '\n')
                .replace('\\t', '\t')
                .replace('\\"', '"')
                .replace('\\\\', '\\'))

    try:
        path = RE_OCTAL_BYTE.sub(_octal_repl, path)
        if has_ab_prefix:
            assert path.startswith('a/') or path.startswith('b/')
            path = path[2:]
    except UnicodeDecodeError:
        logging.error("Error decode path: {}".format(path))

    return path


def _pick_best_path(path_match, rename_match, path_fallback_match):
    if path_match:
        return _decode_path(path_match)

    if rename_match:
        return _decode_path(rename_match, has_ab_prefix=False)

    if path_fallback_match:
        return _decode_path(path_fallback_match)

    return None


def _parse_numstats(text):
    hsh = {"total": {"additions": 0, "deletions": 0, "changes": 0, "total": 0, "files": 0}, "files": {}}
    for line in text.splitlines():

        (raw_insertions, raw_deletions, filename) = line.split("\t")

        if '{' in filename:
            root_path = filename[:filename.find("{")]
            mid_path = filename[filename.find("{") + 1:filename.find("}")].split("=>")[-1].strip()
            end_path = filename[filename.find("}") + 1:]
            filename = root_path + mid_path + end_path
            filename = filename.replace("//", "/")

        if " => " in filename:
            filename = filename.split(" => ")[1]

        insertions = raw_insertions != "-" and int(raw_insertions) or 0
        deletions = raw_deletions != "-" and int(raw_deletions) or 0
        hsh["total"]["additions"] += insertions
        hsh["total"]["deletions"] += deletions
        hsh["total"]["changes"] += insertions + deletions
        hsh["total"]["total"] += insertions + deletions
        hsh["total"]["files"] += 1
        hsh["files"][filename.strip()] = {"filename": filename.strip(), "additions": insertions, "deletions": deletions,
                                          "changes": insertions + deletions}
    return (hsh["total"], hsh["files"])


def _parse_stats(text):
    diffs = dict()

    for line in text.splitlines():
        try:
            line = line
        except Exception as e:
            pass

        if not line.startswith(":"):
            continue

        meta, _, path = line[1:].partition("\t")
        old_mode, new_mode, a_blob_id, b_blob_id, _change_type = meta.split(None, 4)

        change_type = _change_type[0]
        score_str = "".join(_change_type[1:])
        score = int(score_str) if score_str.isdigit() else None
        path = path.strip()
        a_path = path
        b_path = path
        deleted_file = False
        new_file = False
        rename_from = None
        rename_to = None

        a_blob = binascii.a2b_hex(a_blob_id)
        b_blob = binascii.a2b_hex(b_blob_id)

        filename = a_path
        previous_filename = ""
        status = ""
        sha = b_blob_id
        if change_type == "D":
            b_blob_id = None
            deleted_file = True
            filename = a_path
            status = "deleted"
        elif change_type == "A":
            a_blob_id = None
            new_file = True
            filename = a_path
            status = "added"
        elif change_type == "R":
            a_path, b_path = path.split("\t", 1)
            a_path = a_path
            b_path = b_path
            rename_from, rename_to = a_path, b_path
            previous_filename = a_path
            filename = b_path
            status = "renamed"
        elif change_type == "M":
            status = "modified"
        elif change_type == "T":
            filename = a_path
            status = "renamed"

        diff = dict(
            filename=filename, previous_filename=previous_filename, sha=sha,
            status=status, a_path=a_path, b_path=b_path, a_blob_id=a_blob_id,
            a_blob=a_blob, b_blob_id=b_blob_id, b_blob=b_blob,
            a_mode=old_mode, b_mode=new_mode, new_file=new_file,
            deleted_file=deleted_file, rename_from=rename_from, rename_to=rename_to,
            change_type=change_type, score=score, patch=""
        )

        diffs[filename] = diff

    return diffs


def _parse_patch(text):
    diffs = list()
    previous_header = None

    for header in RE_COMMIT_DIFF.finditer(text):
        a_path_fallback, b_path_fallback, old_mode, new_mode, \
        rename_from, rename_to, new_file_mode, deleted_file_mode, \
        a_blob_id, b_blob_id, b_mode, a_path, b_path = header.groups()

        new_file, deleted_file = bool(new_file_mode), bool(deleted_file_mode)
        a_path = _pick_best_path(a_path, rename_from, a_path_fallback)
        b_path = _pick_best_path(b_path, rename_to, b_path_fallback)

        if previous_header is not None:
            patch = text[previous_header.end():header.start()]
            diffs[-1]["patch"] = patch

        a_mode = old_mode or deleted_file_mode or (a_path and (b_mode or new_mode or new_file_mode))
        b_mode = b_mode or new_mode or new_file_mode or (b_path and a_mode)

        a_blob_id = a_blob_id and a_blob_id
        b_blob_id = b_blob_id and b_blob_id

        a_blob = binascii.a2b_hex(a_blob_id) if a_blob_id else a_blob_id
        b_blob = binascii.a2b_hex(b_blob_id) if b_blob_id else b_blob_id

        change_type = ""
        filename = a_path
        previous_filename = ""
        status = ""
        sha = b_blob_id
        if new_file:
            change_type = "A"
            filename = b_path
            status = "added"
        elif deleted_file:
            change_type = "D"
            filename = a_path
            status = "deleted"
        elif a_path != b_path:
            change_type = "R"
            filename = b_path
            previous_filename = a_path
            status = "renamed"
        elif (a_blob and b_blob and a_blob != b_blob) or (not a_blob and not b_blob and a_mode != b_mode):
            change_type = "M"
            status = "modified"

        diff = dict(
            filename=filename, previous_filename=previous_filename, sha=sha,
            status=status, a_path=a_path, b_path=b_path, a_blob_id=a_blob_id,
            a_blob=a_blob, b_blob_id=b_blob_id, b_blob=b_blob,
            a_mode=a_mode and a_mode,
            b_mode=b_mode and b_mode,
            new_file=new_file, deleted_file=deleted_file, rename_from=rename_from,
            rename_to=rename_to, change_type=change_type, score=""
        )

        diffs.append(diff)

        previous_header = header

        if diffs:
            patch = text[header.end():]
            diffs[-1]["patch"] = patch

    dict_diffs = dict()
    for diff in diffs:
        dict_diffs[diff["filename"]] = diff

    return dict_diffs


def execute(commandLine):
    process = subprocess.Popen(commandLine, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out = process.stdout.read().strip().decode("UTF-8")
    error = process.stderr.read().strip().decode("UTF-8")

    if error:
        process.kill()
        if DEBUG:
            logging.error("Execution '{}'".format(repr(commandLine)))
        raise Exception(error)
    return out


def get_commits_sha(start, number):
    all_commits_sha = execute(COMMAND_GET_ALL_COMMITS_SHA)
    all_commits_sha = all_commits_sha.split('\n')
    index = all_commits_sha.index(start)
    commits_sha = all_commits_sha[index:index+number]
    commits_sha.reverse()
    return commits_sha


def _parse_person(text):
    (person_name, person_email, person_date) = text.split("\t")
    person_date = person_date.split(" ")
    person_date = "{}T{}{}".format(person_date[0], person_date[1], person_date[2])
    return {"name": person_name, "email": person_email, "date": person_date}


def request(url, token, data, event):
    headers = {"Content-Type": "application/json",
                "X-Git-Event": event,
                "token": token}
    try:
        session = Session()
        session.mount('http://', HTTPAdapter(max_retries=3))
        session.mount('https://', HTTPAdapter(max_retries=3))
        resp = session.post(url=url, data=data, headers=headers, verify=False, allow_redirects=True)
        result = (resp.status_code, resp.reason)
    except Exception as e:
        print("Request error: ", e)
        result = (None, None)
    return result


def get_project_id(base_url, project_name, token):
    url = base_url + '/api/ssh_v2/hook/fetch/?project_name={}'.format(project_name)
    headers = {"Content-Type": "application/json",
                "token": token}
    try:
        session = Session()
        session.mount('http://', HTTPAdapter(max_retries=3))
        session.mount('https://', HTTPAdapter(max_retries=3))
        resp = session.get(url=url, headers=headers, verify=False, allow_redirects=True)
    except Exception as e:
        print("Request error: ", e)
        return None
    return resp.text


def get_commit_branch(sha):
    branch_list = list()
    output = execute(COMMAND_COMMIT_BRANCH.format(sha))

    for line in output.splitlines():

        if 'HEAD' in line:
            continue

        line = line.replace("*", "")
        line = line.rstrip().lstrip()

        if "refs/remotes/origin/" in line:
            line = line[len("refs/remotes/origin/"):]
        elif "remotes/origin/" in line:
            line = line[len("remotes/origin/"):]
        elif "origin/" in line:
            line = line[len("origin/"):]
        elif "refs/heads/" in line:
            line = line[len("refs/heads/"):]
        elif "heads/" in line:
            line = line[len("heads/"):]

        branch_list.append(line)

    logging.debug("Commit '{}' exist in branches: '{}'".format(sha, len(branch_list)))
    return list(set(branch_list))


def get_commit(sha):
    
    commit_cmd = COMMAND_COMMIT.format(sha)
    if is_windows:
        commit_cmd = commit_cmd.replace('\'', '')
        commit_cmd = commit_cmd.replace('\t', '%x09')

    output = execute(commit_cmd)

    commit_header = RE_COMMIT_HEADER.findall(output)[0]
    commit_numstats = {"additions": 0, "deletions": 0, "changes": 0, "total": 0, "files": 0}

    sha, \
    date, \
    tree, \
    parents, \
    author, \
    committer, \
    message, \
    file_stats, \
    file_numstats, \
    patch = commit_header


    # parents = get_parent_list([parent_sha for parent_sha in parents.split(" ") if parent_sha])

    date = date.split(" ")
    date = "{}T{}{}".format(date[0], date[1], date[2])

    author = _parse_person(author)
    committer = _parse_person(committer)

    commit = dict(
        sha=sha,
        tree=tree,
        # branches=branches,
        parents=parents,
        date=date,
        message=message,
        author=author,
        committer=committer,
        stats=commit_numstats,
        files=[],
        added=[],
        removed=[],
        modified=[]
    )

    if file_numstats:
        commit_numstats, file_numstats = _parse_numstats(file_numstats)
    else:
        file_numstats = {}

    if file_stats:
        file_stats = _parse_stats(file_stats)
    else:
        file_stats = {}

    if patch:
        patch = _parse_patch(patch)
    else:
        patch = {}

    filename_list_1 = []
    filename_list_2 = []
    filename_list_3 = []

    for filename, data in file_numstats.items():
        filename_list_1.append(filename)

    for filename, data in file_stats.items():
        filename_list_2.append(filename)

    for filename, data in patch.items():
        filename_list_3.append(filename)

    for filename in set(filename_list_1 + filename_list_2 + filename_list_3):

        try:
            numstat = file_numstats[filename]
            stat = file_stats[filename]
            diff = patch[filename]
        except Exception as e:
            traceback.print_exc()
            continue

        # if blame:
        #     try:
        #         blame = get_commit_file_blame(filename=filename, sha=sha, patch=diff["patch"])
        #     except Exception as e:
        #         blame = ""
        # else:
        #     blame = ""

        file_object = dict(
            filename=filename,
            additions=numstat["additions"],
            deletions=numstat["deletions"],
            changes=numstat["changes"],
            sha=stat["sha"],
            status=stat["status"],
            previous_filename=stat["previous_filename"],
            patch=diff["patch"],
            # blame=blame or ""
        )

        if stat["status"] == "added":
            commit["added"].append(filename)
        elif stat["status"] == "added":
            commit["added"].append(filename)
        elif stat["status"] == "deleted":
            commit["removed"].append(filename)
        elif stat["status"] == "modified":
            commit["modified"].append(filename)
        elif stat["status"] == "renamed":
            commit["removed"].append(stat["previous_filename"])
            commit["added"].append(filename)
        elif stat["status"] == "unknown":
            commit["modified"].append(filename)

        commit["files"].append(file_object)

    return commit


def wrap_push_event(ref, commit):
    try:
        commits = list()
        commits.append(commit)
        data = {
            "before": commit["sha"],
            "after": commit["sha"],
            "ref": ref,
            "base_ref": "",
            "ref_type": "commit",
            "commits": commits,
        }
        return json.dumps(data)
    except Exception as e:
        logging.debug("Incorrect chunk: '{}'. {}".format(commit, e), exc_info=DEBUG)
        return json.dumps({})


parser = argparse.ArgumentParser(description='Sync a number of commits before a specific commit')


parser.add_argument('--url', type=str, 
                    help='Enter your organization url')
parser.add_argument('--project', type=str,
                    help='Enter project name')
parser.add_argument('--token', type=str,
                    help='The API key to communicate with API')
parser.add_argument('--start', type=str,
                    help='Enter the commit that would be the starter')
parser.add_argument('--number', type=int,
                    help='Enter the number of commits that would be returned')


args = parser.parse_args()

base_url = args.url.rstrip('/')
project = args.project
token = args.token
start = args.start
number = args.number if args.number else 100


project_id = json.loads(get_project_id(base_url=base_url, project_name=project, token=token))["project_id"]
url = base_url + '/api/ssh_v2/hook/{}/'.format(project_id)


def performPush(url, token, start, number):
    sha_list = get_commits_sha(start, number)
    for sha in sha_list:
        commit = get_commit(sha)
        ref = get_commit_branch(sha)[0]
        data = wrap_push_event(ref, commit)
        print(data)

        status_code, content = request(url, token, data, event='push')

performPush(url=url, token=token, start=start, number=number)
