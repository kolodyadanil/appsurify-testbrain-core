# -*- coding: utf-8 -*-
import os
import sys 
from django.conf import settings
from django.template import Template, Context


def generate_hook(hook_url, username, repo_name, api_key):
    dir = os.path.dirname(os.path.abspath(__file__))
    web_hook = open(os.path.join(dir, "hook.tmpl"), "r")
    data = web_hook.read()
    data = data.replace("{{HOOK_URL}}", hook_url)
    data = data.replace("{{USERNAME}}", username)
    data = data.replace("{{PROJECT}}", repo_name)
    data = data.replace("{{API_KEY}}", api_key)
    return data
