# -*- coding: utf-8 -*-
import django

django.setup()

from django.db.models import F, Subquery, OuterRef
from applications.vcs.models import *
from applications.testing.models import *


def main():
    print("Caused start")
    DefectCausedByCommits.objects.all().update(
        created=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        )
    )
    print("Caused end")

    print("Closed start")
    DefectClosedByCommits.objects.all().update(
        created=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        )
    )
    print("Closed end")

    print("Test Areas start")
    TestAssociatedAreas.objects.all().update(
        created=Subquery(
            Area.objects.filter(
                id=OuterRef('area_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            Area.objects.filter(
                id=OuterRef('area_id')
            ).values('created')[:1]
        )
    )
    print("Test areas end")

    print("Test files start")
    TestAssociatedFiles.objects.all().update(
        created=Subquery(
            File.objects.filter(
                id=OuterRef('file_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            File.objects.filter(
                id=OuterRef('file_id')
            ).values('created')[:1]
        )
    )
    print("Test files end")

    print("Commit areas start")
    CommitAreas.objects.all().update(
        created=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            Commit.objects.filter(
                id=OuterRef('commit_id')
            ).values('created')[:1]
        )
    )
    print("Commit areas end")

    print("Area areas start")
    AreaDependencies.objects.all().update(
        created=Subquery(
            Area.objects.filter(
                id=OuterRef('to_area_id')
            ).values('created')[:1]
        ),
        updated=Subquery(
            Area.objects.filter(
                id=OuterRef('to_area_id')
            ).values('created')[:1]
        )
    )
    print("Area areas end")
    return True


if __name__ == "__main__":
    main()
