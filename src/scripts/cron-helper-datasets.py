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
from applications.ml.models import MLModel
from applications.ml.utils import (
    fix_missed_models,
    fix_expired_models,
    fix_broken_models,
    perform_dataset_to_csv
)


@pidfile()
def main():
    fix_missed_models()
    fix_expired_models()
    fix_broken_models()

    for ml_model in MLModel.objects.filter(dataset_status=MLModel.Status.PENDING).order_by("-updated")[:5]:
        try:
            perform_dataset_to_csv(ml_model=ml_model)
        except Exception as exc:
            print(exc)
            continue


if __name__ == "__main__":
    try:
        main()
    except (IOError, BlockingIOError, PidFileAlreadyRunningError) as e:
        sys.exit(123)
