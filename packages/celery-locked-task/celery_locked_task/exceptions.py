# -*- coding: utf-8 -*-


class CeleryLockException(Exception):
    pass


class DuplicateTaskError(CeleryLockException):
    """ Errors acquiring or releasing a lock """
    # NOTE: For backwards compatability, this class derives from ValueError.
    # This was originally chosen to behave like threading.Lock.
    pass


class LockError(CeleryLockException, ValueError):
    """ Errors acquiring or releasing a lock """
    # NOTE: For backwards compatability, this class derives from ValueError.
    # This was originally chosen to behave like threading.Lock.
    pass


class RunError(CeleryLockException, ValueError):
    """ Errors acquiring or releasing a lock """
    # NOTE: For backwards compatability, this class derives from ValueError.
    # This was originally chosen to behave like threading.Lock.
    pass
