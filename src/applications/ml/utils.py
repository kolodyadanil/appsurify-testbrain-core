import logging
import pathlib
import textdistance
import hashlib


logger = logging.getLogger(__name__)


class Statistic(object):
    _context = {}

    _current = 0
    _total = 0
    _success = 0
    _failure = 0

    def __str__(self):
        return f"[{self._current}/{self._total}] ({self._success}/{self._failure})"

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, value):
        self._total = value

    @property
    def current(self):
        return self._current

    @property
    def success(self):
        return self._success

    @property
    def failure(self):
        return self._failure

    def increase_current(self):
        self._current += 1

    def increase_success(self):
        self._success += 1

    def increase_failure(self):
        self._failure += 1

    def reset(self):
        self._total = 0
        self._current = 0
        self._success = 0
        self._failure = 0

    @property
    def progress_percent(self):
        if self._total == 0:
            return 0
        return self._current * 100 // self._total


def similarity(value1, value2):
    value1 = value1.lower()
    value2 = value2.lower()

    return textdistance.damerau_levenshtein.normalized_similarity(value1, value2) +\
        textdistance.sorensen_dice.normalized_similarity(value1, value2) +\
        textdistance.lcsseq.normalized_similarity(value1, value2)


def hash_value(data):
    if isinstance(data, (list, tuple)):
        return [hashlib.md5(i.encode('utf-8')).hexdigest() for i in data]
    return []
