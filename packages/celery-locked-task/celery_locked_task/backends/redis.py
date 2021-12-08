# -*- coding: utf-8 -*-
from __future__ import absolute_import

from redis import Redis
from .base import BaseBackend


class RedisBackend(BaseBackend):

    def __init__(self, *args, **kwargs):
        """
        args and kwargs are forwarded to redis.from_url
        """
        self.redis = Redis.from_url(*args, decode_responses=True, **kwargs)

    def acquire(self, token, task_id, ex=None):
        return not not self.redis.set(token, task_id, nx=True, ex=ex)

    def release(self, token):
        return bool(self.redis.delete(token))

    def reacquire(self, token, task_id, ex=None):
        if not self.locked(token):
            return self.acquire(token, task_id, ex=ex)
        return self.extend(token, additional_time=ex, replace_ttl=True)

    def extend(self, token, additional_time, replace_ttl=False):
        new_ttl = additional_time
        if not replace_ttl:
            cur_ttl = int(self.redis.ttl(token))
            new_ttl += cur_ttl
        return self.redis.expire(token, new_ttl)

    def task_id(self, token):
        return self.redis.get(token)

    def expire_at(self, token):
        return int(self.redis.ttl(token))

    def locked(self, token):
        return bool(self.redis.exists(token))

    def clear(self, key_prefix):
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(cursor=cursor, match=key_prefix + "*")
            for k in keys:
                self.redis.delete(k)
            if cursor == 0:
                break
