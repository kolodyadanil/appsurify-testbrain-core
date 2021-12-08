# -*- coding: utf-8 -*-

import logging
import time

from celery import Task as BaseTask
from celery.exceptions import Reject
from celery.signals import task_received
from celery.utils.imports import symbol_by_name
from celery.utils.log import get_logger
from celery.utils.time import timezone
from celery.worker.request import create_request_cls
from celery.worker.state import task_reserved
from celery.worker.strategy import proto1_to_proto2, hybrid_to_proto2
from kombu.asynchronous.timer import to_timestamp
from kombu.utils.uuid import uuid

try:
    from inspect import signature
except:
    from funcsigs import signature

from .config import Config
from .backends import get_backend
from .utils import generate_token
from .exceptions import RunError
from vine.five import buffer_t


logger = get_logger(__name__)


def clear_locks(app):
    config = Config(app)
    backend = get_backend(config)
    backend.clear(config.key_prefix)


def lock_strategy(task, app, consumer,
            info=logger.info, error=logger.error, task_reserved=task_reserved,
            to_system_tz=timezone.to_system, bytes=bytes, buffer_t=buffer_t,
            proto1_to_proto2=proto1_to_proto2):
    """Default task execution strategy.

    Note:
        Strategies are here as an optimization, so sadly
        it's not very easy to override.
    """
    hostname = consumer.hostname
    connection_errors = consumer.connection_errors
    _does_info = logger.isEnabledFor(logging.INFO)

    # task event related
    # (optimized to avoid calling request.send_event)
    eventer = consumer.event_dispatcher
    events = eventer and eventer.enabled
    send_event = eventer and eventer.send
    task_sends_events = events and task.send_events

    call_at = consumer.timer.call_at
    apply_eta_task = consumer.apply_eta_task
    rate_limits_enabled = not consumer.disable_rate_limits
    get_bucket = consumer.task_buckets.__getitem__
    handle = consumer.on_task_request
    limit_task = consumer._limit_task
    limit_post_eta = consumer._limit_post_eta
    body_can_be_buffer = consumer.pool.body_can_be_buffer
    Request = symbol_by_name(task.Request)
    Req = create_request_cls(Request, task, consumer.pool, hostname, eventer)

    revoked_tasks = consumer.controller.state.revoked

    def task_message_handler(message, body, ack, reject, callbacks, to_timestamp=to_timestamp):
        if body is None and 'args' not in message.payload:
            body, headers, decoded, utc = (
                message.body, message.headers, False, app.uses_utc_timezone(),
            )
            if not body_can_be_buffer:
                body = bytes(body) if isinstance(body, buffer_t) else body
        else:
            if 'args' in message.payload:
                body, headers, decoded, utc = hybrid_to_proto2(message,
                                                               message.payload)
            else:
                body, headers, decoded, utc = proto1_to_proto2(message, body)

        req = Req(
            message,
            on_ack=ack, on_reject=reject, app=app, hostname=hostname,
            eventer=eventer, task=task, connection_errors=connection_errors,
            body=body, headers=headers, decoded=decoded, utc=utc,
        )

        if (req.expires or req.id in revoked_tasks) and req.revoked():
            return

        lock_token = task.generate_token(req.task_name, task_args=req.args, task_kwargs=req.kwargs)
        lock_task_id = task._lock_task_id(lock_token)
        if lock_task_id and (lock_task_id != req.task_id):
            time.sleep(0.5)

            if not headers.get('redelivered'):
                info('Re-Queued task: %s', req)

            req.on_reject(logger, req._connection_errors, True)
            req.acknowledged = False
            req.send_event('task-sent', requeue=True)
            return

        elif lock_task_id and (lock_task_id == req.task_id):
            time.sleep(0.5)

            if not headers.get('redelivered'):
                info('Received on another worker task: %s', req)

            return

        # else:
        #     lock_aquired = task.lock_aquire(lock_token, req.task_id)
        #     if not lock_aquired:
        #         req.on_reject(logger, req._connection_errors, True)
        #         req.acknowledged = False
        #         req.send_event('task-sent', requeue=True)
        #         return

        if _does_info:
            info('Received task: %s', req)

        task_received.send(sender=consumer, request=req)

        if task_sends_events:
            send_event(
                'task-received',
                uuid=req.id, name=req.name,
                args=req.argsrepr, kwargs=req.kwargsrepr,
                root_id=req.root_id, parent_id=req.parent_id,
                retries=req.request_dict.get('retries', 0),
                eta=req.eta and req.eta.isoformat(),
                expires=req.expires and req.expires.isoformat(),
            )

        bucket = None
        eta = None

        if req.eta:
            try:
                if req.utc:
                    eta = to_timestamp(to_system_tz(req.eta))
                else:
                    eta = to_timestamp(req.eta, app.timezone)
            except (OverflowError, ValueError) as exc:
                error("Couldn't convert ETA %r to timestamp: %r. Task: %r",
                      req.eta, exc, req.info(safe=True), exc_info=True)
                req.reject(requeue=False)

        if rate_limits_enabled:
            bucket = get_bucket(task.name)

        if eta and bucket:
            consumer.qos.increment_eventually()
            return call_at(eta, limit_post_eta, (req, bucket, 1), priority=6)
        if eta:
            consumer.qos.increment_eventually()
            call_at(eta, apply_eta_task, (req,), priority=6)
            return task_message_handler
        if bucket:
            return limit_task(req, bucket, 1)

        task_reserved(req)
        if callbacks:
            [callback(req) for callback in callbacks]

        handle(req)

    return task_message_handler


class LockedTask(BaseTask):
    abstract = True
    acks_late = True
    acks_on_failure_or_timeout = True
    reject_on_worker_lost = True

    #: Execution strategy used, or the qualified name of one.
    # Strategy = 'celery.worker.strategy:default'
    Strategy = 'celery_locked_task.locked_task:lock_strategy'

    #: Request class used, or the qualified name of one.
    Request = 'celery.worker.request:Request'

    _lock_config = None
    _lock_backend = None

    lock_expires = None
    lock_renewal_expires = None

    unique_on = None

    requeue_on_duplicate = True

    def __init__(self, *args, **kwargs):
        super(LockedTask, self).__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        lock_token = self.generate_token(self.name, task_args=args, task_kwargs=kwargs)
        task_id = self.request.id
        lock_task_id = self.lock_task_id
        logger.info('Call task: %s[%s - %s]', self.name, task_id, lock_task_id)
        lock_aquired = self.lock_aquire(lock_token, task_id)
        if lock_aquired:
            try:
                logger.info('Executing task: %s[%s - %s]', self.name, task_id, lock_task_id)
                return super(LockedTask, self).__call__(*args, **kwargs)
            # except Exception as exc:
            #     self.lock_release(lock_token)
            #     raise exc
            finally:
                self.lock_release(lock_token)
        elif not lock_aquired:
            exc = RunError('Reject task: {}'.format(task_id))
            raise Reject(exc, requeue=True)

        else:
            logger.info('Executing on another worker task: %s[%s - %s]', self.name, task_id, lock_task_id)
            pass

    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                    link=None, link_error=None, shadow=None, **options):

        task_id = task_id or uuid()
        args = args or []
        kwargs = kwargs or {}
        # lock_token = self.generate_token(self.name, task_args=args, task_kwargs=kwargs)
        # self.lock_aquire(lock_token, task_id)
        return super(LockedTask, self).apply_async(args=args, kwargs=kwargs, task_id=task_id, producer=producer,
                                                   link=link, link_error=link_error, shadow=shadow, **options)
    @property
    def lock_config(self):
        if self._lock_config:
            return self._lock_config
        self._lock_config = Config(self._get_app())
        return self._lock_config

    @property
    def lock_backend(self):
        if self._lock_backend:
            return self._lock_backend
        self._lock_backend = get_backend(self.lock_config)
        return self._lock_backend

    @property
    def lock_expire_at(self):
        lock_token = self.generate_token(self.name, task_args=self.request.args, task_kwargs=self.request.kwargs)
        return self.lock_backend.expire_at(lock_token)

    @property
    def lock_task_id(self):
        lock_token = self.generate_token(self.name, task_args=self.request.args, task_kwargs=self.request.kwargs)
        return self._lock_task_id(lock_token)

    def lock_aquire(self, lock_token, task_id):
        lock_expires = (
            self.lock_expires
            if self.lock_expires is not None
            else self.lock_config.lock_expires
        )
        lock_acquired = self.lock_backend.acquire(lock_token, task_id, ex=lock_expires)
        # if not lock_acquired:
        #     locked_task_id = self._lock_task_id(lock_token)
        #     if locked_task_id == task_id:
        #         return True
        # else:
        #     return lock_acquired
        return lock_acquired

    def lock_reacquire(self, lock_token, task_id):
        lock_expires = (
            self.lock_expires
            if self.lock_expires is not None
            else self.lock_config.lock_expires
        )
        return self.lock_backend.reacquire(lock_token, task_id, ex=lock_expires)

    def lock_extend(self, additional_time, replace_ttl=False):
        lock_token = self.generate_token(self.name, task_args=self.request.args, task_kwargs=self.request.kwargs)
        return self.lock_backend.extend(lock_token, additional_time=additional_time, replace_ttl=replace_ttl)

    def lock_release(self, lock_token):
        return self.lock_backend.release(lock_token)

    def generate_token(self, task_name, task_args=None, task_kwargs=None):
        unique_on = self.unique_on

        if isinstance(unique_on, str):
            unique_on = [unique_on]

        task_args = task_args or []
        task_kwargs = task_kwargs or {}

        if unique_on:

            sig = signature(self.run)
            bound = sig.bind(*task_args, **task_kwargs).arguments

            unique_args = []
            unique_kwargs = {key: bound.get(key) for key in unique_on}

        else:
            unique_args = task_args
            unique_kwargs = task_kwargs

        return generate_token(
            task_name,
            unique_args,
            unique_kwargs,
            key_prefix=self.lock_config.key_prefix,
        )

    def _lock_task_id(self, lock_token):
        task_id = self.lock_backend.task_id(lock_token)
        return task_id if task_id else ''

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        lock_token = self.generate_token(self.name, task_args=args, task_kwargs=kwargs)
        self.lock_release(lock_token)
        super(LockedTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        lock_token = self.generate_token(self.name, task_args=args, task_kwargs=kwargs)
        self.lock_release(lock_token)
        super(LockedTask, self).on_success(retval, task_id, args, kwargs)
