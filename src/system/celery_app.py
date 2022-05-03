# -*- coding: utf-8 -*-
import os

from celery import Celery
from celery import signals  # noqa


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")

app = Celery("testbrain")

app.config_from_object("django.conf:settings", namespace="CELERY")


@signals.setup_logging.connect
def on_celery_setup_logging(*args, **kwargs):
    from logging.config import dictConfig  # noqa
    from django.conf import settings  # noqa

    dictConfig(settings.LOGGING)


app.autodiscover_tasks()


@app.task(bind=True)
def debug(self, a=1, r=2, g=3, timeout=15):
    print(f"{a}\tRequest: {self.request!r}")
    import time
    time.sleep(timeout)
    return {"a": a, "r": r, "g": g, "timeout": timeout}
