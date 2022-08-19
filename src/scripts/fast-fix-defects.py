# -*- coding: utf-8 -*-
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from pidfile import PIDFile, AlreadyRunningError
from applications.testing.models import *
from applications.vcs.models import *


def main(*argv, **kwargs):
    project_id = argv[1]
    print(project_id)
    defects = Defect.objects.filter(project_id=project_id)

    for defect in defects:
        try:
            created_commit = defect.created_by_commit
            closed_commit = defect.closed_commit
            caused_commits = defect.caused_by_commits.first()

            if created_commit is None and closed_commit:
                closed_commit_parent = closed_commit.to_commits.first().from_commit
                defect.caused_by_commits.set([closed_commit_parent, ])

            elif created_commit is None and caused_commits:
                caused_commits_first_child = caused_commits.from_commits.first().to_commit
                defect.closed_commit = caused_commits_first_child
                defect.closed_by_commits.set([caused_commits_first_child, ])

            elif created_commit:
                created_commit_child = created_commit.from_commits.first().to_commit
                defect.caused_by_commits.set([created_commit, ])
                defect.closed_commit = created_commit_child
                defect.closed_by_commits.set([created_commit_child, ])

            defect.status = Defect.STATUS_CLOSED
            defect.type = Defect.TYPE_PROJECT
            defect.save()
        except Exception as exc:
            print(exc)
            continue
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv))
    except Exception as exc:
        sys.exit(100)
