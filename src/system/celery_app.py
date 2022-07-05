# -*- coding: utf-8 -*-
import os

from celery import Celery
from celery import signals  # noqa


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")

app = Celery("testbrain")

app.config_from_object("django.conf:settings", namespace="CELERY")


@signals.after_setup_logger.connect
def on_after_setup_logger(**kwargs):
    from logging.config import dictConfig  # noqa
    from django.conf import settings  # noqa
    dictConfig(settings.LOGGING)
    # import logging
    # logger = logging.getLogger('celery')
    # logger.propagate = False
    # logger = logging.getLogger('celery.app.trace')
    # logger.propagate = False


app.autodiscover_tasks()


@app.task(bind=True)
def debug(self, a=1, r=2, g=3, timeout=15):
    print(f"{a}\tRequest: {self.request!r}")
    import time
    time.sleep(timeout)
    return {"a": a, "r": r, "g": g, "timeout": timeout}
