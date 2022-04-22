# -*- coding: utf-8 -*-
import time
import logging
import contextlib
import random
from hashlib import sha256

from django.core.cache import cache as django_cache


class DistLockException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


@contextlib.contextmanager
def dist_lock(key, attempts=10, expires=300):
    key_hexdigest = sha256(key).hexdigest()
    key = '__d_lock_%s' % key_hexdigest

    got_lock = False
    try:
        got_lock = _acquire_lock(key, attempts, expires)
        yield
    finally:
        if got_lock:
            _release_lock(key)


def _acquire_lock(key, attempts, expires):
    for i in xrange(0, attempts):
        stored = django_cache.add(key, 1, expires)
        if stored:
            return True
        if i != attempts - 1:
            sleep_time = (((i + 1) * random.randint(60, 120)) + 2 ** i) // 2.5
            logging.debug('Sleeping for %s while trying to acquire key %s', sleep_time, key)
            time.sleep(sleep_time)
    raise DistLockException('Could not acquire lock for %s' % key)


def _release_lock(key):
    django_cache.delete(key)


def single_operation(function=None, key="", timeout=None):
    """Ensure only one celery task gets invoked at a time."""

    def _dec(run_func):
        def _caller(*args, **kwargs):

            func_result = None
            have_lock = False
            lock = django_cache.lock(key, timeout=timeout)
            try:
                have_lock = lock.acquire(blocking=False)
                if have_lock:
                    func_result = run_func(*args, **kwargs)
            finally:
                if have_lock:
                    lock.release()
            if func_result:
                return func_result

        return _caller

    return _dec(function) if function is not None else _dec
