from applications.allauth.socialaccount.providers.discord.provider import DiscordProvider
from applications.allauth.socialaccount.providers.oauth2.urls import default_urlpatterns


urlpatterns = default_urlpatterns(DiscordProvider)
