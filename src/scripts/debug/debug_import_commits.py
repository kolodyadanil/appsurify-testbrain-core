from git import Repo
from github import Github
from applications.project.models import Project
from applications.integration.github.models import GithubRepository
from applications.integration.github.utils import processing_commits_fast
from applications.integration.utils import processing_commits, create_or_update_commit
from applications.vcs.models import Commit, Branch


project = Project.objects.get(id=2)
repository = GithubRepository.objects.get(id=1)

git_path = "/Users/whenessel/WebstormProjects/Templates-simple-site"

repo = Repo(git_path)
refs = list([branch.name for branch in repo.branches])

# fast_task_result = processing_commits_fast(project=project, repository=repository)

new_commits = []

for refspec in refs:
    branch, _ = Branch.objects.get_or_create(project=project, name=refspec)
    rev = refspec
    commits = repo.iter_commits(rev=rev, reverse=True)
    commits = list([commit for commit in commits])
    for commit in commits:
        new_commit, _ = create_or_update_commit(project=project, repository=repository, branch=branch,
                                                refspec=refspec, commit=commit)
        new_commits.append(new_commit)

print("Finish")
