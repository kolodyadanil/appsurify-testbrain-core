# -*- coding: utf-8 -*-
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from pidfile import PIDFile, AlreadyRunningError
from applications.ml.commands import perform_prepare_datasets


def main():
    perform_prepare_datasets()
    return 0


if __name__ == "__main__":
    try:
        with PIDFile("cron-helper-datasets.pid"):
            sys.exit(main())
    except (IOError, BlockingIOError) as e:
        sys.exit(123)
    except AlreadyRunningError:
        sys.exit(124)
    except Exception as exc:
        sys.exit(125)
