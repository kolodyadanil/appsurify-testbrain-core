# -*- coding: utf-8 -*-

from abc import abstractmethod


class BaseBackend(object):

    @abstractmethod
    def acquire(self, token, task_id, ex=None):
        """
        Store a lock for given lock value and task ID

        :param token:
        :param task_id:
        :param ex:
        :return:
        """

    @abstractmethod
    def release(self, token):
        """
        Release lock

        :return:
        """

    @abstractmethod
    def reacquire(self, token, task_id, ex=None):
        """
        Re acquire specify lock

        :param token:
        :param task_id:
        :param ex:
        :return:
        """

    @abstractmethod
    def extend(self, token, additional_time, replace_ttl=False):
        """
        Add expire time to specify lock

        :param additional_time:
        :param replace_ttl:
        :return:
        """

    @abstractmethod
    def task_id(self, token):
        """
        Get task ID for given lock

        :param token:
        :return:
        """

    @abstractmethod
    def expire_at(self, token):
        """
        Get expiration time

        :param token:
        :return:
        """

    @abstractmethod
    def locked(self, token):
        """
        Get locked or not locked

        :param token:
        :return:
        """

    @abstractmethod
    def clear(self, key_prefix):
        """
        Clear all locks stored under given key_prefix

        :param key_prefix:
        :return:
        """
