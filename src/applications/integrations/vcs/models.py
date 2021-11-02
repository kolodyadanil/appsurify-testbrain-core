# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Union, AnyStr
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


USER_MODEL = get_user_model()


class Repository(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        verbose_name="project",
        related_name="repositories",
        on_delete=models.CASCADE
    )

    server = models.JSONField(
        verbose_name="server",
        blank=False,
        null=False
    )

    auth = models.JSONField(
        verbose_name="auth",
        default=dict,
        blank=True,
        null=False
    )

    path = models.CharField(
        verbose_name="path",
        max_length=255,
        blank=False,
        null=False
    )

    options = models.JSONField(
        verbose_name="options",
        default=dict,
        blank=True,
        null=False
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = []
        verbose_name = "repository"
        verbose_name_plural = "repositories"

    def __str__(self):
        return f"[{self.server['provider']}] {self.path}"


class Event(models.Model):

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "RECEIVED"
        PENDING = "PENDING", "PENDING"
        STARTED = "STARTED", "STARTED"
        FAILURE = "FAILURE", "FAILURE"
        REJECTED = "REJECTED", "REJECTED"
        SUCCESS = "SUCCESS", "SUCCESS"
        IGNORED = "IGNORED", "IGNORED"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    repository = models.ForeignKey(
        "Repository",
        verbose_name="repository",
        related_name="events",
        on_delete=models.CASCADE
    )

    headers = models.JSONField(
        verbose_name="headers",
        default=dict,
        blank=True,
        null=False
    )

    payload = models.JSONField(
        verbose_name="payload",
        default=dict,
        blank=True,
        null=False
    )

    status = models.CharField(
        verbose_name="status",
        max_length=128,
        default=Status.RECEIVED,
        choices=Status.choices,
        blank=False,
        null=False
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = []
        verbose_name = "event"
        verbose_name_plural = "events"

    def __str__(self):
        return f"[{self.get_status_display()}] {self.repository.path}"


class Change(models.Model):

    repository = models.ForeignKey(
        "Repository",
        verbose_name="repository",
        related_name="changes",
        on_delete=models.CASCADE
    )

    event = models.ForeignKey(
        "Event",
        verbose_name="event",
        related_name="changes",
        null=True,
        on_delete=models.SET_NULL
    )

    branches = models.JSONField(
        verbose_name="branches",
        default=tuple,
        blank=False,
        null=False
    )

    parents = models.JSONField(
        verbose_name="parents",
        default=tuple,
        blank=False,
        null=False
    )

    hexsha = models.CharField(
        verbose_name="hexsha",
        max_length=40,
        blank=False,
        null=False
    )

    tree = models.CharField(
        verbose_name="tree",
        max_length=40,
        blank=False,
        null=False
    )

    message = models.TextField(
        verbose_name="message",
        default="",
        blank=True,
        null=False
    )

    timestamp = models.DateTimeField(
        verbose_name="timestamp",
        blank=False,
        null=False
    )

    author = models.JSONField(
        verbose_name="author",
        default=dict,
        blank=False,
        null=False
    )

    committer = models.JSONField(
        verbose_name="commiter",
        default=dict,
        blank=False,
        null=False
    )

    stats = models.JSONField(
        verbose_name="stats",
        default=dict,
        blank=False,
        null=False
    )
    # {"files": {u'README.md': {'deletions': 3, 'lines': 4, 'insertions': 1}},
    # "total": {'deletions': 3, 'lines': 4, 'insertions': 1, 'files': 1}}

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["timestamp", ]
        unique_together = ["repository", "hexsha", ]
        verbose_name = "change"
        verbose_name_plural = "changes"

    @property
    def display_id(self):
        return f"{self.hexsha[:7]}"

    def __str__(self):
        return f"{self.hexsha}"
