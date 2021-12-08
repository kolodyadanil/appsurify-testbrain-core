# -*- coding: utf-8 -*-
from system.env import env

from kombu import Queue, Exchange


# CELERY
# ------------------------------------------------------------------------------
CELERY_BROKER_URL = env.str("BROKER_URL", default="amqp://guest:guest@localhost:5672//")
CELERY_RESULT_BACKEND = env.str("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 1800,
    "priority_steps": list(range(11)),
    "queue_order_strategy": "priority",
    "max_retries": 10,

}

CELERY_BROKER_HEARTBEAT = 20
CELERY_BROKER_HEARTBEAT_CHECKRATE = 2

CELERY_RESULT_EXPIRES = 60 * 60 * 3  # 3 hours
CELERY_RESULT_PERSISTENT = True
CELERY_RESULT_SERIALIZER = "json"

CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_DEFAULT_EXCHANGE = "default"
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "direct"
CELERY_TASK_DEFAULT_ROUTING_KEY = "default"

CELERY_TASK_QUEUE_MAX_PRIORITY = 100
CELERY_TASK_DEFAULT_PRIORITY = 0

CELERY_TASK_QUEUES = (
    Queue("high", routing_key="high", exchange=Exchange("high"), queue_arguments={"x-max-priority": 100}),
    Queue("normal", routing_key="normal", exchange=Exchange("normal"), queue_arguments={"x-max-priority": 50}),
    Queue("low", routing_key="low", exchange=Exchange("low"), queue_arguments={"x-max-priority": 10}),
    Queue("default", routing_key="default", exchange=Exchange("default"), queue_arguments={"x-max-priority": 0}),

)

CELERY_TASK_ROUTES = {
    '*': {'queue': 'default'},

    'applications.*': {'queue': 'normal', 'priority': 5},

    'applications.integration.tasks.clone_repository_task': {'queue': 'high', 'priority': 100},

    'applications.integration.tasks.fetch_repository_task': {'queue': 'high', 'priority': 80},
    'applications.integration.tasks.processing_commits_task': {'queue': 'high', 'priority': 80},

    'applications.integration.tasks.processing_files_task': {'queue': 'normal', 'priority': 60},
    'applications.integration.tasks.processing_rework_task': {'queue': 'normal', 'priority': 40},
    'applications.integration.tasks.processing_defects_task': {'queue': 'normal', 'priority': 40},

    'applications.integration.tasks.analyze_fast_model_task': {'queue': 'normal', 'priority': 30},
    'applications.integration.tasks.analyze_output_task': {'queue': 'normal', 'priority': 30},

    'applications.testing.tasks.add_caused_by_commits_task': {'queue': 'low', 'priority': 20},
    'applications.testing.tasks.add_closed_by_commits_task': {'queue': 'low', 'priority': 20},

    'applications.integration.tasks.analyze_slow_models_task': {'queue': 'low', 'priority': 10},

    'applications.testing.tasks.build_test_prioritization_ml_models': {'queue': 'low', 'priority': 40},
    'applications.testing.tasks.build_test_prioritization_ml_model_for_test_suite': {'queue': 'low', 'priority': 40},

}

CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_SEND_SENT_EVENT = True

CELERY_TASK_SOFT_TIME_LIMIT = 60 * 60 * 12  # 12 hours
CELERY_TASK_TIME_LIMIT = 60 * 60 * 24 * 2  # 2 days

CELERY_WORKER_POOL = env.str("WORKER_POOL", default="prefork")
CELERY_WORKER_CONCURRENCY = env.int("WORKER_CONCURRENCY", default=4)
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int("WORKER_PREFETCH_MULTIPLIER", default=1)

CELERY_WORKER_CONSUMER = "celery.worker.consumer:Consumer"

CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int("WORKER_MAX_TASKS_PER_CHILD", default=20)

CELERY_WORKER_TIMER_PRECISION = 2.0
CELERY_WORKER_LOST_WAIT = 15.0
CELERY_WORKER_AUTOSCALER = "celery.worker.autoscale:Autoscaler"

CELERY_WORKER_ENABLE_REMOTE_CONTROL = True
CELERY_WORKER_SEND_TASK_EVENTS = True

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "create_ml_models_for_tests_prioritization": {
        "task": "applications.testing.tasks.build_test_prioritization_ml_models",
        "schedule": 60 * 60 * 6,  # Start task every 2 hours
    },
}
