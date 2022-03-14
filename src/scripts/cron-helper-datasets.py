# -*- coding: utf-8 -*-
import os
import sys
import time
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from pid.decorator import pidfile
from pid import PidFileAlreadyRunningError

from django.conf import settings

from applications.testing.models import TestSuite
from applications.ml.models import MLDataset
from applications.ml.utils import (
    fix_missed_datasets, fix_expired_datasets, fix_broken_datasets,
    perform_dataset_to_csv
)


@pidfile()
def main():
    fix_missed_datasets()
    fix_expired_datasets()
    fix_broken_datasets()

    for ml_dataset in MLDataset.objects.filter(status=MLDataset.Status.PENDING)[:10]:
        try:
            perform_dataset_to_csv(ml_dataset=ml_dataset)
        except Exception as exc:
            print(exc)
            continue


if __name__ == "__main__":
    try:
        main()
    except (IOError, BlockingIOError, PidFileAlreadyRunningError) as e:
        sys.exit(123)
