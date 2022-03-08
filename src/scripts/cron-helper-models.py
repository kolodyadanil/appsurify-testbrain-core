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
from applications.ml.neural_network import MLTrainer
from applications.ml.models import MLModel
from applications.ml.utils import (
    fix_missed_models, fix_expired_models, fix_broken_models,
    perform_model_train
)


@pidfile()
def main():
    fix_missed_models()
    fix_expired_models()
    fix_broken_models()

    for ml_model in MLModel.objects.filter(status=MLModel.Status.PENDING)[:5]:
        try:
            perform_model_train(ml_model=ml_model)
        except Exception as exc:
            print(exc)
            continue


if __name__ == "__main__":
    try:
        main()
    except (IOError, BlockingIOError, PidFileAlreadyRunningError) as e:
        sys.exit(123)
