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

from applications.ml.utils import (
    fix_missed,
    fix_expired,
    fix_broken
)


def main():
    fix_missed()
    fix_expired()
    fix_broken()


if __name__ == "__main__":
    try:
        with PIDFile("cron-helper-checker.pid"):
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
