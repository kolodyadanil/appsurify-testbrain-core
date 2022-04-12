import warnings
import sys
import argparse
import subprocess
import json
import re
import logging
import os

#: OS Windows
is_windows = (os.name == 'nt')

#: OS MacOS or Linux
is_posix = (os.name == 'posix')


try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.sessions import Session
    from requests.adapters import Retry
except ImportError:
    warnings.warn("Please install 'requests' library, e.g. 'pip install requests'."\
                  "Then run the command again.")
    sys.exit(1)


COMMAND_GET_ALL_COMMITS_SHA = "git log --reflog --pretty=format:%H"
COMMAND_COMMIT = "git show --reverse --first-parent --raw --numstat --abbrev=40 --full-index -p -M --pretty=format:'Commit:\t%H%nDate:\t%ai%nTree:\t%T%nParents:\t%P%nAuthor:\t%an\t%ae\t%ai%nCommitter:\t%cn\t%ce\t%ci%nMessage:\t%s%n' {}"
COMMAND_COMMIT_BRANCH = "git branch --contains {}"

DEBUG = True
COMMIT_COUNT = 10
BASE_URL = 'http://0.0.0.0:9000/api/ssh_v2/hook/'

RE_COMMIT_HEADER = re.compile(
    r"""^Commit:\t(?P<sha>[0-9A-Fa-f]+)\nDate:\t(?P<date>.*)\nTree:\t(?P<tree>[0-9A-Fa-f]+)\nParents:\t(?P<parents>.*)\nAuthor:\t(?P<author>.*)\nCommitter:\t(?P<committer>.*)\nMessage:\t(?P<message>.*)?(?:\n\n|$)?(?P<file_stats>(?:^:.+\n)+)?(?P<file_numstats>(?:.+\t.*\t.*\n)+)?(?:\n|\n\n|$)?(?P<patch>(?:diff[ ]--git(?:.+\n)+)+)?(?:\n\n|$)?""",
    re.VERBOSE | re.MULTILINE)


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


def get_project_id(project_name, token):
    url = BASE_URL + 'fetch/?project_name={}'.format(project_name)
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

    # if file_numstats:
    #     commit_numstats, file_numstats = _parse_numstats(file_numstats)
    # else:
    #     file_numstats = {}

    # if file_stats:
    #     file_stats = _parse_stats(file_stats)
    # else:
    #     file_stats = {}

    # if patch:
    #     patch = _parse_patch(patch)
    # else:
    #     patch = {}

    filename_list_1 = []
    filename_list_2 = []
    filename_list_3 = []

    # for filename, data in file_numstats.items():
    #     filename_list_1.append(filename)

    # for filename, data in file_stats.items():
    #     filename_list_2.append(filename)

    # for filename, data in patch.items():
    #     filename_list_3.append(filename)

    # for filename in set(filename_list_1 + filename_list_2 + filename_list_3):

    #     if isinstance(filename, str):
    #         filename = filename.decode('utf-8', errors='ignore')

    #     try:
    #         numstat = file_numstats[filename]
    #         stat = file_stats[filename]
    #         diff = patch[filename]
    #     except Exception as e:
    #         traceback.print_exc()
    #         continue

    #     if blame: ".join(sha)
    #         try:
    #             blame = get_commit_file_blame(filename=filename, sha=sha, patch=diff["patch"])
    #         except Exception as e:
    #             blame = ""
    #     else:
    #         blame = ""

    #     file_object = dict(
    #         filename=filename,
    #         additions=numstat["additions"],
    #         deletions=numstat["deletions"],
    #         changes=numstat["changes"],
    #         sha=stat["sha"],
    #         status=stat["status"],
    #         previous_filename=stat["previous_filename"],
    #         patch=diff["patch"],
    #         blame=blame or ""
    #     )

    #     if stat["status"] == "added":
    #         commit["added"].append(filename)
    #     elif stat["status"] == "added":
    #         commit["added"].append(filename)
    #     elif stat["status"] == "deleted":
    #         commit["removed"].append(filename)
    #     elif stat["status"] == "modified":
    #         commit["modified"].append(filename)
    #     elif stat["status"] == "renamed":
    #         commit["removed"].append(stat["previous_filename"])
    #         commit["added"].append(filename)
    #     elif stat["status"] == "unknown":
    #         commit["modified"].append(filename)

    #     commit["files"].append(file_object)

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
        logging.debug("Incorrect chunk: '{}'. {}".format(','.join(commit_list), e), exc_info=DEBUG)
        return json.dumps({})


parser = argparse.ArgumentParser(description='Sync a number of commits before a specific commit')


# parser.add_argument('--url', type=str, 
#                     help='Enter domain/api/ssh_v2/hook/project_id')
parser.add_argument('--project', type=str, 
                    help='Enter project name')
parser.add_argument('--token', type=str,
                    help='The API key to communicate with API')
parser.add_argument('--start', type=str,
                    help='Enter the commit that would be the starter')
parser.add_argument('--number', type=int,
                    help='Enter the number of commits that would be returned')


args = parser.parse_args()

# url = args.url
project = args.project
token = args.token
start = args.start
number = args.number if args.number else 100


def performPush(token, start, number):
    sha_list = get_commits_sha(start, number)
    for sha in sha_list:
        commit = get_commit(sha)
        ref = get_commit_branch(sha)[0]
        data = wrap_push_event(ref, commit)
        
        project_id = json.loads(get_project_id(project_name=project, token=token))["project_id"]
        url = BASE_URL + '{}/'.format(project_id)
        
        status_code, content = request(url, token, data, event='push')

performPush(token, start, number)
