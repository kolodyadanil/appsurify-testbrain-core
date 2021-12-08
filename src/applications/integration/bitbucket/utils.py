# import os
#
# from git import Repo
# from django.conf import settings
# from datetime import datetime
# import re
#
# from applications.integration.bitbucket.models import BitbucketRepository
# from applications.integration.bitbucket.api import get_or_refresh_token
# from applications.project.models import Project
# from applications.vcs.models import Commit, Branch, File, FileChange, Area
#
# filename_regex = re.compile(r'\{.*\s=>\s.*\}')
#
#
# def sync_full_commits(project_id):
#     try:
#         repository = BitbucketRepository.objects.get(project_id=project_id)
#     except BitbucketRepository.DoesNotExist:
#         return False, 'Project not connected with bitbucket'
#
#     project = Project.objects.get(pk=repository.project_id)
#     token = get_or_refresh_token(repository.id)
#     repo_url = 'https://x-token-auth:{}@bitbucket.org/{}'.format(token, repository.bitbucket_repository_name)
#
#     repo = Repo('{storage_path}/organizations/{organization_id}/projects/{project_id}'.format(
#         storage_path=settings.STORAGE_ROOT,
#         organization_id=project.organization_id,
#         project_id=repository.project_id))
#
#     repo.delete_remote('origin')
#     repo.create_remote('origin', url=repo_url)
#
#     branches = repo.remote('origin').fetch()
#
#     for branch in branches:
#         branch_name = branch.name.split('/')[-1]
#         new_branch, created = Branch.objects.get_or_create(project_id=project_id, name=branch_name)
#         commits = repo.iter_commits(rev=branch.name)
#
#         for commit in reversed(list(commits)):
#             try:
#                 commit = Commit.objects.get(project_id=project_id, sha=commit.hexsha)
#                 commit.branches.add(new_branch)
#             except Commit.DoesNotExist:
#                 create_commit(commit, repository, new_branch, repo=repo)
#
#
# def sync_new_commits(project_id):
#     try:
#         repository = BitbucketRepository.objects.get(project_id=project_id)
#     except BitbucketRepository.DoesNotExist:
#         return False, 'Project not connected with bitbucket'
#
#     project = Project.objects.get(pk=repository.project_id)
#     token = get_or_refresh_token(repository.id)
#     repo_url = 'https://x-token-auth:{}@bitbucket.org/{}'.format(token, repository.bitbucket_repository_name)
#
#     repo = Repo('{storage_path}/organizations/{organization_id}/projects/{project_id}'.format(
#         storage_path=settings.STORAGE_ROOT,
#         organization_id=project.organization_id,
#         project_id=repository.project_id))
#
#     repo.delete_remote('origin')
#     repo.create_remote('origin', url=repo_url)
#
#     branches = repo.remote('origin').fetch()
#
#     commits_hashes = []
#
#     for branch in branches:
#         branch_name = branch.name.split('/')[-1]
#         new_branch, created = Branch.objects.get_or_create(project_id=project_id, name=branch_name)
#         commits = repo.iter_commits(rev=branch.name)
#
#         for commit in commits:
#             sha_commit = commit.hexsha
#
#             try:
#                 Commit.objects.get(project_id=project_id, sha=sha_commit)
#                 continue
#             except Commit.DoesNotExist:
#                 create_commit(commit, repository, new_branch, repo=repo)
#                 commits_hashes.append(sha_commit)
#
#     return commits_hashes
#
#
# def create_commit(commit, repository, branch, repo=None):
#     new_commit = Commit()
#     sha_commit = commit.hexsha
#
#     area_default = Area.get_default(project=repository.project)
#
#     new_commit.project_id = repository.project_id
#     new_commit.repo_id = sha_commit
#     new_commit.sha = sha_commit
#     new_commit.display_id = sha_commit[:7]
#     new_commit.author = {
#         'email': commit.author.email,
#         'name': commit.author.name,
#         'date': datetime.fromtimestamp(commit.authored_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
#     }
#     new_commit.committer = {
#         'email': commit.committer.email,
#         'name': commit.committer.name,
#         'date': datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%dT%H:%M:%SZ'),
#     }
#     new_commit.message = commit.message[:255]
#     new_commit.stats = {
#         'deletions': commit.stats.total.get('deletions', 0),
#         'additions': commit.stats.total.get('insertions', 0),
#         'total': commit.stats.total.get('lines', 0)
#     }
#     new_commit.timestamp = datetime.fromtimestamp(commit.authored_date)
#     new_commit.save()
#
#     new_commit.branches.add(branch)
#
#     index_number = 0
#
#     for parent in commit.parents:
#         index_number += 1
#         parent_commit_sha = parent.hexsha
#
#         parent_commit, created = Commit.objects.get_or_create(project=repository.project, sha=parent_commit_sha)
#         parent_commit.branches.add(branch)
#         new_commit.add_parent(parent_commit, index_number)
#
#     parent = commit.parents[0] if commit.parents else repo.tree('4b825dc642cb6eb9a060e54bf8d69288fbee4904')
#
#     diffs = {}
#
#     for diff in parent.diff(commit.hexsha, create_patch=True):
#         path = diff.a_path
#         diff_type = get_diff_type(diff)
#
#         if diff_type in ['A', 'M', 'R']:
#             path = diff.b_path
#
#         diffs[path] = diff
#
#     for obj_path, stats in commit.stats.files.items():
#         obj_path = prepare_path(obj_path)
#
#         diff = diffs.get(obj_path)
#
#         if diff.a_blob:
#             file_sha = diff.a_blob.hexsha
#         elif diff.a_blob:
#             file_sha = diff.b_blob.hexsha
#         elif diff.b_blob and get_diff_type(diff) in ['A', 'M', 'R']:
#             file_sha = diff.b_blob.hexsha
#         else:
#             file_sha = str
#
#         created = False
#         filename = obj_path
#         filename_list = filename.split('/')
#         parent = None
#
#         for name in filename_list:
#             project_file, created = File.objects.get_or_create(project=repository.project, filename=name, parent=parent)
#             parent = project_file
#             if project_file.parent:
#                 if project_file.parent.get_descendant_count() - 1 == project_file.parent.get_descendants().filter(
#                         areas__in=project_file.parent.areas.exclude(id=area_default.id)).count():
#                     project_file.areas.add(*project_file.parent.areas.exclude(id=area_default.id))
#
#         previous_filename = diff.rename_from
#
#         if not previous_filename:
#             previous_filename = str()
#
#         if created or previous_filename:
#             project_file.sha = file_sha
#             project_file.save()
#
#         patch = diff.diff
#
#         status_choice = {
#             'A': FileChange.STATUS_ADDED,
#             'M': FileChange.STATUS_MODIFIED,
#             'D': FileChange.STATUS_DELETED,
#             'R': FileChange.STATUS_RENAMED,
#             'T': FileChange.STATUS_MODIFIED,
#         }
#         current_diff_type = get_diff_type(diff)
#
#         try:
#             patch = patch.decode('utf-8')
#         except UnicodeDecodeError:
#             patch = ''
#
#         project_file.add_changes(
#             commit=new_commit,
#             additions=stats.get('insertions'),
#             deletions=stats.get('deletions'),
#             changes=stats.get('lines'),
#             status=status_choice.get(current_diff_type),
#             patch=patch,
#             previous_filename=previous_filename,
#         )
#
#         for area in filename.split('/')[1::-1]:
#             try:
#                 file_area = Area.objects.get(project=repository.project, name=area)
#                 project_file.areas.add(file_area)
#             except Area.DoesNotExist:
#                 continue
#
#         new_commit.areas.add(*project_file.areas.all())
#         project_file.areas.add(area_default)
#         new_commit.areas.add(area_default)
#
#     return new_commit
#
#
# def get_diff_type(diff):
#     """
#     Determines the type of the diff by looking at the diff flags.
#     """
#     if diff.renamed:
#         return 'R'
#
#     if diff.deleted_file:
#         return 'D'
#
#     if diff.new_file:
#         return 'A'
#
#     return 'M'
#
#
# def prepare_path(path):
#     path = path.replace('"', '').decode('string_escape')
#
#     if '=>' not in path:
#         return path
#
#     if filename_regex.findall(path):
#         extracted_filename = filename_regex.search(path).group()
#         correct_filename = extracted_filename.split('=> ')[-1].rstrip('}')
#
#         path = path.replace(extracted_filename, correct_filename)
#     else:
#         path = path.split(' => ')[-1]
#
#     path = os.path.normpath(path)
#     return path
#
#
# def clone_repository(repository):
#     repository_name = repository.bitbucket_repository_name
#     token = get_or_refresh_token(repository.id)
#     url_clone = 'https://x-token-auth:{}@bitbucket.org/{}'.format(token, repository_name)
#     project = Project.objects.get(pk=repository.project_id)
#     Repo.clone_from(url_clone, '{}/organizations/{}/projects/{}'.format(settings.STORAGE_ROOT,
#                                                                         project.organization_id,
#                                                                         repository.project_id))
#
#
# def pull_repository(repository):
#     repo = Repo('{}/organizations/{}/projects/{}'.format(settings.STORAGE_ROOT,
#                                                          repository.project.organization_id,
#                                                          repository.project_id))
#     token = get_or_refresh_token(repository.id)
#     repo_url = 'https://x-token-auth:{}@bitbucket.org/{}'.format(token, repository.bitbucket_repository_name)
#     repo.delete_remote('origin')
#     repo.create_remote('origin', url=repo_url)
#     repo.remote('origin').fetch()
