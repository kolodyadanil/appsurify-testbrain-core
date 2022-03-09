# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.utils import timezone
from applications.testing.utils.db_create_functions import create_functions


class Command(BaseCommand):
    help = 'Create DB functions'

    def handle(self, *args, **kwargs):
        create_functions()
