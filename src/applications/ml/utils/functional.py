
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
    def progress_percent(self):
        if self._total == 0:
            return 0
        return self._current * 100 // self._total

    @property
    def progress_percent_float(self):
        if self._total == 0:
            return 0
        return self._current * 100 / self._total

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
