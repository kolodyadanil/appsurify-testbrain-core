# -*- coding: utf-8 -*-
"""
Management utility to create organization.
"""
from __future__ import unicode_literals

import getpass
import unicodedata
import sys
import time
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.management import get_default_username
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from django.core.management.base import BaseCommand, CommandError
from applications.notification.daemon import NotificationDaemon


class Command(BaseCommand):
    help = 'Notification daemon'
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument('type', action='store', type=str, choices=('daemon', 'cron'), help='')
        parser.add_argument('action', action='store', type=str, choices=('start', 'stop', 'restart', 'status'), help='')

    def handle(self, *args, **options):
        run_type = options['type']
        action = options['action']

        NOTIFICATION_DAEMON = NotificationDaemon()

        try:
            if run_type == 'daemon':

                if action == 'start':
                    self.stdout.write(self.style.NOTICE('Notification daemon starting...'))
                    NOTIFICATION_DAEMON.start()

                elif action == 'stop':
                    self.stdout.write(self.style.NOTICE('Notification daemon stopping...'))
                    NOTIFICATION_DAEMON.stop()
                    self.stdout.write(self.style.SUCCESS('Notification daemon stopped'))

                elif action == 'restart':
                    self.stdout.write(self.style.NOTICE('Notification daemon restarting...'))
                    NOTIFICATION_DAEMON.restart()
                    self.stdout.write(self.style.SUCCESS('Notification daemon restarted'))

                elif action == 'status':
                    pid = NOTIFICATION_DAEMON.status()
                    if pid:
                        self.stdout.write(self.style.SUCCESS('Notification daemon is running as pid {}'.format(pid)))
                    else:
                        self.stdout.write(self.style.ERROR('Notification daemon is not running'))
            elif run_type == 'cron':

                # for env_k, env_v in os.environ.items():
                #     self.stdout.write("{}: {}".format(env_k, env_v))
                #
                # self.stdout.write("start checking notifications")

                NOTIFICATION_DAEMON.cron()

            sys.exit(0)
        except Exception as e:
            # self.stderr.write("\nOperation cancelled.")
            self.stdout.write(self.style.ERROR('{error}'.format(error=e)))
            sys.exit(1)
