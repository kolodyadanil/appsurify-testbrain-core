from importlib import import_module

from django.conf.urls import include, url

from applications.allauth.socialaccount import providers

from . import app_settings


urlpatterns = [
    url(r'^', include('applications.allauth.account.urls'))
]
# urlpatterns = []

if app_settings.SOCIALACCOUNT_ENABLED:
    urlpatterns += [
        url(r'^social/', include('applications.allauth.socialaccount.urls'))
    ]


for provider in providers.registry.get_list():
    try:
        prov_mod = import_module(provider.get_package() + '.urls')
    except ImportError:
        continue
    prov_urlpatterns = getattr(prov_mod, 'urlpatterns', None)
    if prov_urlpatterns:
        urlpatterns += prov_urlpatterns
