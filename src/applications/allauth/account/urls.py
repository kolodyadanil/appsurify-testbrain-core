# -*- coding: utf-8 -*-
from django.conf.urls import url

from . import views


urlpatterns = [

    url(r'^login/$', views.login, name='account_login'),
    url(r'^logout/$', views.logout, name='account_logout'),

    url(r'^signup/$', views.signup, name='account_signup'),

    url(r'^signup/v2/$', views.signup_v2, name='account_signup_v2'),

    url(r'^invite/$', views.invite, name='account_invite'),
    url(r'^confirm-email/(?P<key>[-:\w]+)/$', views.confirm_email, name='account_confirm_email'),
    url(r'^applications/', views.social_application_list, name='account_applications'),

    url(r'^profile/$', views.user_profile, name='account_profile'),
    url(r'^users/$', views.user_list, name='account_users'),
    url(r'^users/(?P<pk>[0-9]+)/$', views.user_retrieve, name='account_user_retrieve'),

    url(r"^email/$", views.email, name='account_email'),

    url(r'^password/set/$', views.password_set, name='account_set_password'),

    url(r"^password/reset/$", views.password_reset, name='account_reset_password'),
    url(r"^password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$", views.password_reset_from_key, name='account_reset_password_from_key'),

    url(r'^check-username/$', views.check_username, name='account_check_username'),
    url(r'^check-user-email/$', views.check_user_email, name='account_check_user_email'),
    url(r'^check-user-password/$', views.check_user_password, name='account_check_user_password'),

    url(r'^change-user-password/$', views.change_user_password, name='account_change_user_password'),
]
