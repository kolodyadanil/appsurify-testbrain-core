# -*- coding: utf-8 -*-
import os
import sys
import time
import django
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from pidfile import PIDFile, AlreadyRunningError

from django.conf import settings

from applications.testing.models import TestSuite
from applications.ml.models import MLModel
from applications.ml.utils import (
    fix_missed,
    fix_expired,
    fix_broken,
    perform_dataset_to_csv,
    perform_multi_dataset_to_csv
)


def main():
    fix_missed()
    fix_expired()
    fix_broken()

    print("Get TestSuites for storing datasets...")
    queryset = TestSuite.objects.filter(
        models__dataset_status=MLModel.Status.PENDING).distinct().order_by("-updated")[:20]

    print(f"Total TestSuites: {queryset.count()}")
    for test_suite in queryset:
        MLModel.objects.filter(test_suite=test_suite).update(updated=timezone.now())
        try:
            result = perform_multi_dataset_to_csv(test_suite=test_suite)
            # result = perform_dataset_to_csv(test_suite=test_suite)
            print(f"<TestSuite: {test_suite.id}> - {result}")
        except Exception as e:
            print(e)
            continue


if __name__ == "__main__":
    try:
        with PIDFile("cron-helper-datasets.pid"):
            print('Process started')
            main()
    except (IOError, BlockingIOError) as e:
        sys.exit(123)
    except AlreadyRunningError:
        # print('Already running.')
        sys.exit(124)
    except Exception as e:
        print(e)
        sys.exit(125)
