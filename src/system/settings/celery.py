# -*- coding: utf-8 -*-
from system.env import env

from kombu import Queue, Exchange
from celery.schedules import crontab


CELERY_SINGLETON_BACKEND_URL = env.str("REDIS_URL", default="redis://localhost:6379/0")

# CELERY
# ------------------------------------------------------------------------------
CELERY_BROKER_URL = env.str("BROKER_URL", default="amqp://guest:guest@localhost:5672//")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"

CELERY_TIMEZONE = "UTC"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 1800,
    "priority_steps": list(range(101)),
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
    Queue('default', Exchange('default'), routing_key='default', queue_arguments={'x-max-priority': 100}),
    Queue('immediate', Exchange('immediate'), routing_key='immediate', queue_arguments={'x-max-priority': 100}),
    Queue('processing', Exchange('processing'), routing_key='processing', queue_arguments={'x-max-priority': 100}),
    Queue('analyze', Exchange('analyze'), routing_key='analyze', queue_arguments={'x-max-priority': 100}),
    Queue('common', Exchange('common'), routing_key='common', queue_arguments={'x-max-priority': 100}),
    Queue('build', Exchange('build'), routing_key='build', queue_arguments={'x-max-priority': 100}),
)

CELERY_TASK_ROUTES = {
    '*': {'queue': 'default', 'priority': 50},
    'celery.ping': {'queue': 'default', 'priority': 50},
    'applications.*': {'queue': 'default', 'priority': 50},

    # immediate
    'applications.integration.tasks.processing_commits_fast_task': {'queue': 'immediate', 'priority': 100},
    'applications.integration.tasks.clone_repository_task': {'queue': 'immediate', 'priority': 90},

    # processing
    'applications.integration.tasks.fetch_repository_task': {'queue': 'processing', 'priority': 100},
    'applications.integration.ssh_v2.tasks.fetch_commits_task_v2': {'queue': 'processing', 'priority': 100},
    'applications.integration.tasks.processing_commits_task': {'queue': 'processing', 'priority': 90},
    'applications.integration.tasks.processing_files_task': {'queue': 'processing', 'priority': 80},
    'applications.integration.ssh_v2.tasks.processing_commit_file_task_v2': {'queue': 'processing', 'priority': 80},

    # analyze 1
    'applications.integration.tasks.processing_rework_task': {'queue': 'analyze', 'priority': 100},
    'applications.integration.ssh_v2.tasks.calculate_rework_task_v2': {'queue': 'analyze', 'priority': 100},
    'applications.integration.tasks.processing_defects_task': {'queue': 'analyze', 'priority': 90},
    'applications.integration.ssh_v2.tasks.import_defects_task_v2': {'queue': 'analyze', 'priority': 90},

    # analyze 2
    'applications.integration.tasks.analyze_fast_model_task': {'queue': 'analyze', 'priority': 80},
    'applications.integration.ssh_v2.tasks.fast_model_analyzer_task': {'queue': 'analyze', 'priority': 80},
    'applications.integration.tasks.analyze_slow_models_task': {'queue': 'analyze', 'priority': 70},
    'applications.integration.ssh_v2.tasks.slow_models_analyzer_task': {'queue': 'analyze', 'priority': 70},
    'applications.integration.tasks.analyze_output_task': {'queue': 'analyze', 'priority': 60},
    'applications.integration.ssh_v2.tasks.output_analyse_task': {'queue': 'analyze', 'priority': 60},
    'applications.testing.tasks.add_association_for_test': {'queue': 'analyze', 'priority': 50},

    # common
    'applications.testing.tasks.add_caused_by_commits_task': {'queue': 'common', 'priority': 50},
    'applications.testing.tasks.add_closed_by_commits_task': {'queue': 'common', 'priority': 50},

    # default
    'applications.testing.tasks.periodic_add_association': {'queue': 'default', 'priority': 50},
    'applications.vcs.tasks.create_area_from_folders_task': {'queue': 'default', 'priority': 50},
    'applications.api.payments.tasks.update_organization_plan_task': {'queue': 'default', 'priority': 50},

}

CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_SEND_SENT_EVENT = True

CELERY_TASK_SOFT_TIME_LIMIT = 60 * 60 * 1  # 1 hour
CELERY_TASK_TIME_LIMIT = 60 * 60 * 6  # 6 hours

CELERY_WORKER_CONSUMER = "celery.worker.consumer:Consumer"
CELERY_WORKER_AUTOSCALER = "celery.worker.autoscale:Autoscaler"

CELERY_WORKER_POOL = env.str("WORKER_POOL", default="prefork")
CELERY_WORKER_POOL_RESTARTS = True
CELERY_WORKER_CONCURRENCY = env.int("WORKER_CONCURRENCY", default=2)
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int("WORKER_PREFETCH_MULTIPLIER", default=1)
# CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int("WORKER_MAX_TASKS_PER_CHILD", default=10)

CELERY_WORKER_TIMER_PRECISION = 1.0
CELERY_WORKER_LOST_WAIT = 30.0

CELERY_WORKER_ENABLE_REMOTE_CONTROL = True
CELERY_WORKER_SEND_TASK_EVENTS = True

CELERY_ENABLE_REMOTE_CONTROL = True

CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    # "periodic_add_association": {
    #     "task": "applications.testing.tasks.periodic_add_association",
    #     "schedule": crontab(hour=8, minute=0, day_of_week="saturday"),
    # },
    "create_area_from_folders_every_day": {
        "task": "applications.vcs.tasks.create_area_from_folders_task",
        "schedule": crontab(minute=0, hour=0),
    },
    "update_org_plan_every_6_hours": {
        "task": "applications.vcs.tasks.create_area_from_folders_task",
        "schedule": crontab(minute=0, hour='*/6'),
    },
    "update_test_run_statistics": {
        "task": "applications.testing.tasks.update_materialized_view",
        "schedule": crontab(minute='*/5'),
    },
    "cleanup_vcs_items": {
        "task": "applications.vcs.clean_duplicates_from_vcs",
        "schedule": crontab(minute='*/30'),
    },
}

CELERYD_POOL_RESTARTS = CELERY_WORKER_POOL_RESTARTS

CELERY_HIJACK_ROOT_LOGGER = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = True
