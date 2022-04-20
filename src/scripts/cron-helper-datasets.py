# -*- coding: utf-8 -*-
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from pidfile import PIDFile, AlreadyRunningError
from applications.ml.utils import perform_prepare_models


def main():
    perform_prepare_models()
    return


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
