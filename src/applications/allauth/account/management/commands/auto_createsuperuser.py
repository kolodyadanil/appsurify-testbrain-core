from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.conf import settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@appsurify.com", "adminadmin")

        if not Site.objects.filter(name=settings.BASE_SITE_DOMAIN, domain=settings.BASE_SITE_DOMAIN).exists():
            Site.objects.create(name=settings.BASE_SITE_DOMAIN, domain=settings.BASE_SITE_DOMAIN)

